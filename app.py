# Importa módulos Flask e de banco de dados
from flask import Flask, render_template, request, redirect, url_for, session
from database import users, routines
import bcrypt
from bson.objectid import ObjectId
from datetime import datetime, timedelta

# Inicializa o aplicativo Flask
app = Flask(__name__)
# Chave secreta para gerenciar sessões (substitua por uma real!)
app.secret_key = 'your_secret_key_here' 

# Função para verificar se o usuário está logado
def is_logged_in():
    return 'user_id' in session

# Rota para a página inicial (login e cadastro)
@app.route('/')
def index():
    if is_logged_in():
        return redirect(url_for('dashboard'))
    return render_template('index.html')

# Rota para processar o cadastro de um novo usuário
@app.route('/register', methods=['POST'])
def register():
    email = request.form['email']
    password = request.form['password'].encode('utf-8')
    name = request.form['name']

    # Checa se o usuário já existe
    if users.find_one({'email': email}):
        return 'E-mail já cadastrado!'

    # Criptografa a senha antes de salvar
    hashed_password = bcrypt.hashpw(password, bcrypt.gensalt())
    
    user_id = users.insert_one({
        'name': name,
        'email': email,
        'password_hash': hashed_password
    }).inserted_id

    session['user_id'] = str(user_id)
    return redirect(url_for('dashboard'))

# Rota para processar o login
@app.route('/login', methods=['POST'])
def login():
    email = request.form['email']
    password = request.form['password'].encode('utf-8')

    user = users.find_one({'email': email})

    # Verifica a senha
    if user and bcrypt.checkpw(password, user['password_hash']):
        session['user_id'] = str(user['_id'])
        return redirect(url_for('dashboard'))
    else:
        return 'E-mail ou senha incorretos!'

# Rota para sair da conta
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

# Rota para o painel do usuário
@app.route('/dashboard')
def dashboard():
    if not is_logged_in():
        return redirect(url_for('index'))
    
    user_id = session['user_id']
    user = users.find_one({'_id': ObjectId(user_id)})
    
    # Busca todas as rotinas do usuário logado
    user_routines = list(routines.find({'user_id': ObjectId(user_id)}))
    
    return render_template('dashboard.html', user=user, routines=user_routines)

# Rota para adicionar uma nova rotina
@app.route('/add_routine', methods=['GET', 'POST'])
def add_routine():
    if not is_logged_in():
        return redirect(url_for('index'))

    if request.method == 'POST':
        user_id = session['user_id']
        pacient_name = request.form['pacient_name']
        med_name = request.form['med_name']
        instructions = request.form['instructions']
        total_qty = int(request.form['total_qty'])
        frequency_hours = int(request.form['frequency_hours'])
        first_dose = datetime.fromisoformat(request.form['first_dose'])

        # Cria a rotina no banco de dados
        routines.insert_one({
            'user_id': ObjectId(user_id),
            'pacient_name': pacient_name,
            'med_name': med_name,
            'instructions': instructions,
            'total_qty': total_qty,
            'remaining_qty': total_qty,
            # last_dose começa como None, já que a primeira dose ainda não foi tomada
            'last_dose': None, 
            'frequency_hours': frequency_hours,
            'next_dose': first_dose
        })
        return redirect(url_for('dashboard'))

    return render_template('routine_form.html')

# Rota para editar uma rotina existente
@app.route('/edit_routine/<routine_id>', methods=['GET', 'POST'])
def edit_routine(routine_id):
    if not is_logged_in():
        return redirect(url_for('index'))
    
    routine = routines.find_one({'_id': ObjectId(routine_id)})
    
    if request.method == 'POST':
        # Atualiza a rotina com os novos dados do formulário
        pacient_name = request.form['pacient_name']
        med_name = request.form['med_name']
        instructions = request.form['instructions']
        total_qty = int(request.form['total_qty'])
        frequency_hours = int(request.form['frequency_hours'])
        first_dose_str = request.form['first_dose']
        
        # Converte a string de data/hora para um objeto datetime
        first_dose = datetime.fromisoformat(first_dose_str)
        
        # Recalcula a próxima dose com base na nova primeira dose e frequência
        new_next_dose = first_dose + timedelta(hours=frequency_hours)
        
        routines.update_one(
            {'_id': ObjectId(routine_id)},
            {'$set': {
                'pacient_name': pacient_name,
                'med_name': med_name,
                'instructions': instructions,
                'total_qty': total_qty,
                'remaining_qty': total_qty,
                'frequency_hours': frequency_hours,
                'next_dose': new_next_dose
            }}
        )
        return redirect(url_for('dashboard'))
        
    return render_template('routine_form.html', routine=routine)

# Rota para deletar uma rotina
@app.route('/delete_routine/<routine_id>', methods=['POST'])
def delete_routine(routine_id):
    if not is_logged_in():
        return redirect(url_for('index'))
    
    # Deleta a rotina do banco de dados
    routines.delete_one({'_id': ObjectId(routine_id)})
    
    return redirect(url_for('dashboard'))

# Rota para marcar uma dose como tomada
@app.route('/take_dose/<routine_id>', methods=['POST'])
def take_dose(routine_id):
    if not is_logged_in():
        return redirect(url_for('index'))

    routine = routines.find_one({'_id': ObjectId(routine_id)})
    
    if routine and routine['remaining_qty'] > 0:
        # Pega o horário atual para registro da última dose
        dose_time = datetime.now()
        
        # Atualiza a quantidade
        new_remaining_qty = routine['remaining_qty'] - 1
        
        # Calcula a próxima dose adicionando a frequência à data da próxima dose agendada
        new_next_dose = routine['next_dose'] + timedelta(hours=routine['frequency_hours'])

        routines.update_one(
            {'_id': ObjectId(routine_id)},
            {'$set': {
                'remaining_qty': new_remaining_qty,
                'last_dose': dose_time,
                'next_dose': new_next_dose
            }}
        )

    return redirect(url_for('dashboard'))
    
# Rota para reabastecer uma rotina
@app.route('/refill_routine/<routine_id>', methods=['POST'])
def refill_routine(routine_id):
    if not is_logged_in():
        return redirect(url_for('index'))

    routine = routines.find_one({'_id': ObjectId(routine_id)})

    if routine:
        routines.update_one(
            {'_id': ObjectId(routine_id)},
            {'$set': {
                'remaining_qty': routine['total_qty']
            }}
        )

    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    app.run(debug=True)

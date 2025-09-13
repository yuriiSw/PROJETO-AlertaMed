# Importa módulos Flask e de banco de dados
from flask import Flask, render_template, request, redirect, url_for, session
from database import users, routines, doses # Agora 'doses' é importado corretamente
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
        'password': hashed_password
    }).inserted_id

    session['user_id'] = str(user_id)
    return redirect(url_for('dashboard'))

# Rota para processar o login do usuário
@app.route('/login', methods=['POST'])
def login():
    email = request.form['email']
    password = request.form['password'].encode('utf-8')

    user = users.find_one({'email': email})

    if user and bcrypt.checkpw(password, user['password']):
        session['user_id'] = str(user['_id'])
        return redirect(url_for('dashboard'))
    else:
        return 'E-mail ou senha inválidos!'

# Rota para o dashboard do usuário
@app.route('/dashboard')
def dashboard():
    if not is_logged_in():
        return redirect(url_for('index'))
    
    user_id = session['user_id']
    user = users.find_one({'_id': ObjectId(user_id)})
    
    # Pega as rotinas do usuário
    user_routines = routines.find({'user_id': ObjectId(user_id)})
    
    # Ordena as rotinas pela próxima dose
    sorted_routines = sorted(list(user_routines), key=lambda r: r.get('next_dose', datetime.max))

    return render_template('dashboard.html', user=user, routines=sorted_routines)

# Rota para adicionar uma nova rotina
@app.route('/add_routine', methods=['GET', 'POST'])
def add_routine():
    if not is_logged_in():
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        user_id = session['user_id']
        med_name = request.form['med_name']
        pacient_name = request.form['pacient_name']
        dose_qty = float(request.form['dose_qty'])
        total_qty = float(request.form['total_qty'])
        frequency_hours = int(request.form['frequency_hours'])
        first_dose_str = request.form['first_dose']
        instructions = request.form.get('instructions', '')
        unit = request.form['unit']
        
        # Converte a data e hora
        first_dose = datetime.strptime(first_dose_str, '%Y-%m-%dT%H:%M')

        routines.insert_one({
            'user_id': ObjectId(user_id),
            'med_name': med_name,
            'pacient_name': pacient_name,
            'dose_qty': dose_qty,
            'total_qty': total_qty,
            'remaining_qty': total_qty,
            'frequency_hours': frequency_hours,
            'first_dose': first_dose,
            'next_dose': first_dose,
            'instructions': instructions,
            'unit': unit
        })
        
        return redirect(url_for('dashboard'))
    
    return render_template('routine_form.html')

# Rota para editar uma rotina existente
@app.route('/edit_routine/<routine_id>', methods=['GET', 'POST'])
def edit_routine(routine_id):
    if not is_logged_in():
        return redirect(url_for('index'))
    
    routine = routines.find_one({'_id': ObjectId(routine_id)})
    
    if not routine:
        return 'Rotina não encontrada!', 404
        
    if request.method == 'POST':
        med_name = request.form['med_name']
        pacient_name = request.form['pacient_name']
        dose_qty = float(request.form['dose_qty'])
        total_qty = float(request.form['total_qty'])
        remaining_qty = float(request.form['remaining_qty'])
        frequency_hours = int(request.form['frequency_hours'])
        first_dose_str = request.form['first_dose']
        instructions = request.form.get('instructions', '')
        unit = request.form['unit']

        # Converte a data e hora
        first_dose = datetime.strptime(first_dose_str, '%Y-%m-%dT%H:%M')
        
        routines.update_one(
            {'_id': ObjectId(routine_id)},
            {'$set': {
                'med_name': med_name,
                'pacient_name': pacient_name,
                'dose_qty': dose_qty,
                'total_qty': total_qty,
                'remaining_qty': remaining_qty,
                'frequency_hours': frequency_hours,
                'first_dose': first_dose,
                'instructions': instructions,
                'unit': unit
            }}
        )
        
        return redirect(url_for('dashboard'))
        
    return render_template('routine_form.html', routine=routine)

# Rota para deletar uma rotina
@app.route('/delete_routine/<routine_id>', methods=['POST'])
def delete_routine(routine_id):
    if not is_logged_in():
        return redirect(url_for('index'))
    
    routines.delete_one({'_id': ObjectId(routine_id)})
    return redirect(url_for('dashboard'))

# Rota para sair da sessão
@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('index'))

# Rota para tomar uma dose
@app.route('/take_dose/<routine_id>', methods=['POST'])
def take_dose(routine_id):
    if not is_logged_in():
        return redirect(url_for('index'))
    
    routine = routines.find_one({'_id': ObjectId(routine_id)})
    
    if routine and routine['remaining_qty'] > 0:
        new_remaining_qty = routine['remaining_qty'] - routine['dose_qty']
        dose_time = datetime.now()
        
        # Calcula a próxima dose
        new_next_dose = dose_time + timedelta(hours=routine['frequency_hours'])
        
        routines.update_one(
            {'_id': ObjectId(routine_id)},
            {'$set': {
                'remaining_qty': new_remaining_qty,
                'last_dose': dose_time,
                'next_dose': new_next_dose
            }}
        )

        # Adiciona um registro da dose na nova coleção 'doses'
        doses.insert_one({
            'routine_id': ObjectId(routine_id),
            'dose_time': dose_time
        })

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
            {'$set': {'remaining_qty': routine['total_qty']}}
        )

    return redirect(url_for('dashboard'))

# NOVA ROTA: Exibe o histórico de doses de uma rotina
@app.route('/dose_history/<routine_id>')
def dose_history(routine_id):
    if not is_logged_in():
        return redirect(url_for('index'))

    # Pega os dados da rotina
    routine = routines.find_one({'_id': ObjectId(routine_id)})
    if not routine:
        return 'Rotina não encontrada!', 404
        
    # Pega o histórico de doses para essa rotina, ordenado por data
    dose_history_list = list(doses.find({'routine_id': ObjectId(routine_id)}).sort('dose_time', -1))

    return render_template('history.html', routine=routine, doses=dose_history_list)
    
# NOVA ROTA: Rota para a página de redefinição de senha (resolve o erro)
@app.route('/reset_password')
def reset_password():
    return render_template('reset_password.html')

if __name__ == '__main__':
    app.run(debug=True)

from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_apscheduler import APScheduler
from database import users, routines, doses
import bcrypt
from bson.objectid import ObjectId
from datetime import datetime, timedelta
import os
from werkzeug.utils import secure_filename

# Inicializa o aplicativo Flask
app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

# Pasta para uploads
UPLOAD_FOLDER = os.path.join('static', 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Configuração e inicialização do APScheduler
class Config:
    SCHEDULER_API_ENABLED = True
app.config.from_object(Config())
scheduler = APScheduler()

# Rota para a página inicial (login e cadastro)
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

# Rota para processar o cadastro de um novo usuário
@app.route('/register', methods=['POST'])
def register():
    email = request.form['email']
    password = request.form['password'].encode('utf-8')
    name = request.form['name']

    if users.find_one({'email': email}):
        flash('E-mail já cadastrado!', 'error')
        return redirect(url_for('index'))

    hashed_password = bcrypt.hashpw(password, bcrypt.gensalt())

    user_id = users.insert_one({
        'name': name,
        'email': email,
        'password': hashed_password
    }).inserted_id

    session['user_id'] = str(user_id)
    flash('Cadastro realizado com sucesso!', 'success')
    return redirect(url_for('dashboard'))

# Rota para processar o login do usuário
@app.route('/login', methods=['POST'])
def login():
    email = request.form['email']
    password = request.form['password'].encode('utf-8')

    user = users.find_one({'email': email})

    if user and bcrypt.checkpw(password, user['password']):
        session['user_id'] = str(user['_id'])
        flash('Login bem-sucedido!', 'success')
        return redirect(url_for('dashboard'))
    else:
        flash('E-mail ou senha inválidos!', 'error')
        return redirect(url_for('index'))

# Rota para o dashboard do usuário
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('index'))
    
    user_id = session['user_id']
    user = users.find_one({'_id': ObjectId(user_id)})
    
    all_routines = list(routines.find({'user_id': ObjectId(user_id)}))
    
    # Separar rotinas pendentes das futuras
    now = datetime.now()
    pending_routines = []
    upcoming_routines = []
    
    for routine in all_routines:
        if routine.get('next_dose') and routine['next_dose'] <= now + timedelta(minutes=30):
            pending_routines.append(routine)
        else:
            upcoming_routines.append(routine)

    # Ordenar as rotinas futuras por próxima dose
    sorted_upcoming_routines = sorted(upcoming_routines, key=lambda r: r.get('next_dose', datetime.max))

    # Adicionando a lógica para o painel de resumo
    refill_count = 0
    for routine in all_routines:
        if routine.get('remaining_qty', 0) <= routine.get('dose_qty', 0) * 2: # Exemplo: menos que 2 doses
            refill_count += 1
    
    return render_template('dashboard.html', 
        user=user, 
        pending_routines=pending_routines,
        upcoming_routines=sorted_upcoming_routines,
        refill_count=refill_count
    )

# Rota para adicionar uma nova rotina
@app.route('/add_routine', methods=['GET', 'POST'])
def add_routine():
    if 'user_id' not in session:
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
        
        first_dose = datetime.strptime(first_dose_str, '%Y-%m-%dT%H:%M')

        treatment_end_date_str = request.form.get('treatment_end_date', '')
        if treatment_end_date_str:
            treatment_end_date = datetime.strptime(treatment_end_date_str, '%Y-%m-%d')
        else:
            treatment_end_date = None
        
        prescription_image = None
        if 'prescription_image' in request.files:
            file = request.files['prescription_image']
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                unique_filename = f"{ObjectId()}_{filename}"
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_filename))
                prescription_image = unique_filename

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
            'unit': unit,
            'notified': False,
            'treatment_end_date': treatment_end_date,
            'prescription_image': prescription_image
        })
        
        flash('Rotina adicionada com sucesso!', 'success')
        return redirect(url_for('dashboard'))
    
    return render_template('routine_form.html', routine=None)

# Rota para editar uma rotina existente
@app.route('/edit_routine/<routine_id>', methods=['GET', 'POST'])
def edit_routine(routine_id):
    if 'user_id' not in session:
        return redirect(url_for('index'))
    
    routine = routines.find_one({'_id': ObjectId(routine_id)})
    
    if not routine:
        flash('Rotina não encontrada!', 'error')
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        med_name = request.form['med_name']
        pacient_name = request.form['pacient_name']
        dose_qty = float(request.form['dose_qty'])
        total_qty = float(request.form['total_qty'])
        frequency_hours = int(request.form['frequency_hours'])
        first_dose_str = request.form['first_dose']
        instructions = request.form.get('instructions', '')
        unit = request.form['unit']

        first_dose = datetime.strptime(first_dose_str, '%Y-%m-%dT%H:%M')
        
        remaining_qty = total_qty - (routine['total_qty'] - routine['remaining_qty'])
        if remaining_qty < 0: remaining_qty = 0
        
        new_next_dose = first_dose

        treatment_end_date_str = request.form.get('treatment_end_date', '')
        if treatment_end_date_str:
            treatment_end_date = datetime.strptime(treatment_end_date_str, '%Y-%m-%d')
        else:
            treatment_end_date = None

        prescription_image = routine.get('prescription_image')
        if 'prescription_image' in request.files:
            file = request.files['prescription_image']
            if file and file.filename and allowed_file(file.filename):
                if prescription_image:
                    old_path = os.path.join(app.config['UPLOAD_FOLDER'], prescription_image)
                    if os.path.exists(old_path):
                        os.remove(old_path)
                
                filename = secure_filename(file.filename)
                unique_filename = f"{ObjectId()}_{filename}"
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_filename))
                prescription_image = unique_filename
        
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
                'next_dose': new_next_dose,
                'notified': False,
                'instructions': instructions,
                'unit': unit,
                'treatment_end_date': treatment_end_date,
                'prescription_image': prescription_image
            }}
        )
        
        flash('Rotina atualizada com sucesso!', 'success')
        return redirect(url_for('dashboard'))
        
    return render_template('routine_form.html', routine=routine)

# Rota para deletar uma rotina
@app.route('/delete_routine/<routine_id>', methods=['POST'])
def delete_routine(routine_id):
    if 'user_id' not in session:
        return redirect(url_for('index'))
    
    routine = routines.find_one({'_id': ObjectId(routine_id)})
    if routine and routine.get('prescription_image'):
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], routine['prescription_image'])
        if os.path.exists(file_path):
            os.remove(file_path)
    
    routines.delete_one({'_id': ObjectId(routine_id)})
    flash('Rotina removida com sucesso!', 'success')
    return redirect(url_for('dashboard'))

# Rota para sair da sessão
@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('Sessão encerrada com sucesso.', 'info')
    return redirect(url_for('index'))

# Rota para tomar uma dose (CORRIGIDA)
@app.route('/take_dose/<routine_id>', methods=['POST'])
def take_dose(routine_id):
    try:
        if 'user_id' not in session:
            return jsonify({'success': False, 'message': 'Não autenticado.'}), 401
        
        routine_obj_id = ObjectId(routine_id)
        routine = routines.find_one({'_id': routine_obj_id})
        
        if not routine:
            return jsonify({'success': False, 'message': 'Rotina não encontrada.'}), 404
        
        # Garante que as quantidades são tratadas como números, mesmo que o MongoDB as tenha salvo como strings
        remaining_qty = float(routine.get('remaining_qty', 0))
        dose_qty = float(routine.get('dose_qty', 0))

        if remaining_qty >= dose_qty:
            new_remaining_qty = remaining_qty - dose_qty
            dose_time = datetime.now()
            
            frequency_hours = int(routine.get('frequency_hours', 24))
            new_next_dose = dose_time + timedelta(hours=frequency_hours)
            
            routines.update_one(
                {'_id': routine_obj_id},
                {'$set': {
                    'remaining_qty': new_remaining_qty,
                    'last_dose': dose_time,
                    'next_dose': new_next_dose,
                    'notified': False
                }}
            )

            doses.insert_one({
                'routine_id': routine_obj_id,
                'dose_time': dose_time
            })

            # Formata a quantidade restante para exibir corretamente na dashboard
            if routine.get('unit') in ['ml', 'gramas']:
                formatted_remaining_qty = f'{new_remaining_qty:.2f}'
            else:
                formatted_remaining_qty = f'{new_remaining_qty:.0f}'

            return jsonify({
                'success': True,
                'message': 'Dose registrada com sucesso!',
                'new_next_dose': new_next_dose.strftime('%d/%m/%Y às %H:%M'),
                'new_remaining_qty': formatted_remaining_qty,
                'total_qty': '{:.2f}'.format(routine['total_qty']) if routine.get('unit') in ['ml', 'gramas'] else '{:.0f}'.format(routine['total_qty']),
                'unit': routine.get('unit')
            })
        else:
            return jsonify({'success': False, 'message': 'Quantidade de medicamento insuficiente.'})
            
    except Exception as e:
        print(f"Erro ao registrar dose: {e}")
        return jsonify({'success': False, 'message': 'Ocorreu um erro interno ao registrar a dose.'}), 500

# Rota para reabastecer uma rotina
@app.route('/refill_routine/<routine_id>', methods=['POST'])
def refill_routine(routine_id):
    if 'user_id' not in session:
        return redirect(url_for('index'))

    routine = routines.find_one({'_id': ObjectId(routine_id)})

    if routine:
        routines.update_one(
            {'_id': ObjectId(routine_id)},
            {'$set': {'remaining_qty': routine['total_qty']}}
        )
        flash('Rotina reabastecida com sucesso!', 'success')
    else:
        flash('Rotina não encontrada!', 'error')

    return redirect(url_for('dashboard'))

# Rota para exibir o histórico de doses de uma rotina
@app.route('/dose_history/<routine_id>')
def dose_history(routine_id):
    if 'user_id' not in session:
        return redirect(url_for('index'))

    routine = routines.find_one({'_id': ObjectId(routine_id)})
    if not routine:
        flash('Rotina não encontrada!', 'error')
        return redirect(url_for('dashboard'))
        
    dose_history_list = list(doses.find({'routine_id': ObjectId(routine_id)}).sort('dose_time', -1))

    return render_template('history.html', routine=routine, doses=dose_history_list)

# --- ROTAS DE REDEFINIÇÃO DE SENHA (SIMPLIFICADAS PARA PROJETO DE FACULDADE) ---

# Rota para a página de solicitação de redefinição de senha
@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        user = users.find_one({'email': email})

        if user:
            session['reset_email'] = email
            flash('E-mail validado. Agora, digite sua nova senha.', 'info')
            return redirect(url_for('reset_password_local'))
        else:
            flash('E-mail não encontrado.', 'error')
            
    return render_template('forgot_password.html')

# Rota para a página de redefinição de senha (local)
@app.route('/reset_password_local', methods=['GET', 'POST'])
def reset_password_local():
    if 'reset_email' not in session:
        flash('Acesso negado. Por favor, digite seu e-mail para redefinir a senha.', 'warning')
        return redirect(url_for('forgot_password'))

    user = users.find_one({'email': session['reset_email']})
    
    if not user:
        flash('Usuário não encontrado. Por favor, tente novamente.', 'error')
        session.pop('reset_email', None)
        return redirect(url_for('forgot_password'))

    if request.method == 'POST':
        new_password = request.form['new_password'].encode('utf-8')
        confirm_password = request.form['confirm_password'].encode('utf-8')

        if new_password != confirm_password:
            flash('As senhas não coincidem.', 'error')
            return render_template('reset_password.html')
        
        hashed_password = bcrypt.hashpw(new_password, bcrypt.gensalt())
        users.update_one({'_id': user['_id']}, {'$set': {'password': hashed_password}})
        
        session.pop('reset_email', None)

        flash('Sua senha foi redefinida com sucesso! Você pode fazer login agora.', 'success')
        return redirect(url_for('index'))

    return render_template('reset_password.html')

# Função de notificação agendada
@scheduler.task('interval', id='check_notifications', seconds=10)
def check_notifications():
    with app.app_context():
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Verificando rotinas para notificações...")
        
        now = datetime.now()
        due_routines = routines.find({
            'next_dose': {
                '$lte': now + timedelta(minutes=10)
            },
            'notified': False
        })
        
        for routine in due_routines:
            time_to_dose = routine['next_dose'] - now
            minutes_to_dose = int(time_to_dose.total_seconds() / 60)
            
            dose_info = f"{routine['dose_qty']} {routine['unit']}"

            if routine.get('treatment_end_date'):
                treatment_info = f"Tratamento: Termina em {routine['treatment_end_date'].strftime('%d/%m/%Y')}"
            else:
                treatment_info = "Tratamento: Uso Contínuo"
            
            if minutes_to_dose > 0:
                print(f"--- ATENÇÃO: Lembrete (10 min antes) ---")
                print(f"Paciente: {routine['pacient_name']}")
                print(f"Medicação: {routine['med_name']}")
                print(f"Dose: {dose_info}")
                print(treatment_info)
                if routine['instructions']:
                    print(f"Instruções: {routine['instructions']}")
                print(f"Próxima dose em ~{minutes_to_dose} minutos.")
                print("---------------------------------------")
            else:
                print(f"--- ATENÇÃO: HORA DA DOSE ---")
                print(f"Paciente: {routine['pacient_name']}")
                print(f"Medicação: {routine['med_name']}")
                print(f"Dose: {dose_info}")
                print(treatment_info)
                if routine['instructions']:
                    print(f"Instruções: {routine['instructions']}")
                print("Hora de tomar o medicamento!")
                print("---------------------------------------")
            
            routines.update_one(
                {'_id': routine['_id']},
                {'$set': {'notified': True}}
            )

if __name__ == '__main__':
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
    
    scheduler.init_app(app)
    scheduler.start()
    app.run(debug=True)
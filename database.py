from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from bson.objectid import ObjectId
import bcrypt

class Database:
    def __init__(self, db_name='medication_db'):
        # Conecta ao MongoDB
        self.client = MongoClient('mongodb://localhost:27017/')
        self.db = self.client[db_name]
        self.users = self.db['users']
        self.routines = self.db['routines']

        # Verifica a conexão
        try:
            self.client.admin.command('ping')
            print("Conexão com o MongoDB estabelecida com sucesso!")
        except ConnectionFailure:
            print("Erro: Falha na conexão com o MongoDB. Verifique se o servidor está rodando.")

    def add_user(self, name, email, password):
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        user_data = {
            'name': name,
            'email': email,
            'password': hashed_password
        }
        return self.users.insert_one(user_data).inserted_id

    def login_user(self, email, password):
        user = self.users.find_one({'email': email})
        if user and bcrypt.checkpw(password.encode('utf-8'), user['password']):
            return user
        return None

    def add_routine(self, user_id, med_name, dose, schedule, start_date):
        routine_data = {
            'user_id': ObjectId(user_id),
            'med_name': med_name,
            'dose': dose,
            'schedule': schedule,
            'start_date': start_date
        }
        return self.routines.insert_one(routine_data).inserted_id

    def get_routines_by_user(self, user_id):
        return list(self.routines.find({'user_id': ObjectId(user_id)}))
    
    def delete_routine(self, routine_id):
        self.routines.delete_one({'_id': ObjectId(routine_id)})

# Cria uma instância da classe Database
db_instance = Database()
users = db_instance.users
routines = db_instance.routines
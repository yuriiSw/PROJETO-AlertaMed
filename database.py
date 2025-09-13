from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from bson.objectid import ObjectId
import bcrypt

# Conecta ao MongoDB
# Certifique-se de que o MongoDB está a ser executado em localhost:27017
client = MongoClient('mongodb://localhost:27017/')
db = client['medication_db']

# Coleções do banco de dados (variáveis globais)
users = db['users']
routines = db['routines']
doses = db['doses']

# Verifica a conexão com o banco de dados
try:
    client.admin.command('ping')
    print("Conexão com o MongoDB estabelecida com sucesso!")
except ConnectionFailure:
    print("Erro: Falha na conexão com o MongoDB. Por favor, verifique se o servidor está a ser executado.")

# Este arquivo não tem mais a classe Database, pois o seu app.py importa as coleções diretamente.

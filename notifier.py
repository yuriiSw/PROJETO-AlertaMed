from database import routines
from datetime import datetime, timedelta
import time
from bson.objectid import ObjectId

# Este script deve ser executado separadamente para verificar as notificações.
# Para simplificar, as notificações serão impressas no console.

def check_notifications():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Verificando rotinas para notificações...")
    
    now = datetime.now()
    
    # Busca rotinas cuja próxima dose está entre 10 minutos no futuro e agora.
    # Isso garante que as notificações sejam enviadas nos 10 minutos que antecedem a dose.
    due_routines = routines.find({
        'next_dose': {
            '$lte': now + timedelta(minutes=10),
            '$gte': now - timedelta(minutes=1)
        }
    })
    
    for routine in due_routines:
        # Calcula a diferença de tempo
        time_to_dose = routine['next_dose'] - now
        minutes_to_dose = int(time_to_dose.total_seconds() / 60)
        
        # Lógica de notificação
        if minutes_to_dose > 0:
            print(f"--- ATENÇÃO: Lembrete (10 min antes) ---")
            print(f"Paciente: {routine['pacient_name']}")
            print(f"Medicação: {routine['med_name']}")
            print(f"Próxima dose em ~{minutes_to_dose} minutos.")
            print("---------------------------------------")
        elif minutes_to_dose <= 0:
            print(f"--- ATENÇÃO: HORA DA DOSE ---")
            print(f"Paciente: {routine['pacient_name']}")
            print(f"Medicação: {routine['med_name']}")
            print("Hora de tomar o medicamento!")
            print("---------------------------------------")

if __name__ == '__main__':
    print("Iniciando o sistema de notificação. Verificando a cada 60 segundos...")
    while True:
        try:
            check_notifications()
        except Exception as e:
            print(f"Erro ao verificar notificações: {e}")
        time.sleep(60) # Espera 60 segundos antes de verificar novamente

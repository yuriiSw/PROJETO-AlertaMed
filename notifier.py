from database import routines
from datetime import datetime, timedelta
import time

# Este script deve ser executado separadamente para verificar as notificações.
# Para simplificar, as notificações serão impressas no console.

def check_notifications():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Verificando rotinas para notificações...")
    
    now = datetime.now()
    # Verifica rotinas que precisam de notificação 10 minutos antes ou na hora exata.
    # A verificação é feita em um intervalo de 11 minutos para garantir que a notificação
    # de 10 minutos seja enviada.
    ten_minutes_from_now = now + timedelta(minutes=11)
    
    due_routines = routines.find({
        'next_dose': {'$lt': ten_minutes_from_now}
    })
    
    for routine in due_routines:
        # Calcula a diferença de tempo
        time_to_dose = routine['next_dose'] - now
        minutes_to_dose = int(time_to_dose.total_seconds() / 60)
        
        # Lógica de notificação
        if minutes_to_dose <= 10 and minutes_to_dose > 0:
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

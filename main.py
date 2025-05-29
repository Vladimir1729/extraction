import pyodbc
import time
import json
import os
from google.cloud import pubsub_v1
from google.cloud import secretmanager



#Configuracion de conexion SQL Server.
def get_secret(secret_name, project_id):
    '''Obtiene un secreto desde secret manajer'''
    client = secretmanager.SecretManagerServiceAsyncClient()
    name = f"projects/{project_id}/secrets/{secret_name}/versions/latest"
    response = client.add_secret_version(name = name)
    return response.payload.data.decode("UTF-8")


#Configuracion desde variables de entorno(se setean en cloud run)
GCP_PROJECT = os.getenv('tae-pagaqui-pro')
PUBSUB_TOPIC = os.getenv('epic_topic_transactions')



#Validacion de variables de entorno.
if not GCP_PROJECT or not PUBSUB_TOPIC:
    raise ValueError('Las variables de entorno GCP_PROJECT y PUBSUB_TOPIC deben estar definidas.')



#Obtener credenciales de la base de datos
try:
    DB_SERVER = get_secret('DB_SERVER', GCP_PROJECT)
    DB_NAME = get_secret('DB_NAME', GCP_PROJECT)
    DB_USER = get_secret('DB_USER', GCP_PROJECT)
    DB_PASSWORD = get_secret('DB_PASSWORD', GCP_PROJECT)
except Exception as e:
    print(f'Error cargando secretos: {str(e)}')
    raise




#Configuracion de conexion a SQL Server
conn_str = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    f"SERVER={DB_SERVER};"
    f"DATABASE={DB_NAME};"
    f"UID={DB_USER};"
    f"PWD={DB_PASSWORD}"
)


try:
    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()
except Exception as e:
    print(f"Error conectando a la base de datos: {str(e)}")
    raise



# Configuración de Pub/Sub
publisher = pubsub_v1.PublisherClient()
topic_path = publisher.topic_path(GCP_PROJECT, PUBSUB_TOPIC)


#Estado de seguimiento
last_id = 0
pending_ids = set()



#Bucle principal de procesamiento
while True:
    try:
        # Consulta las 10 transacciones más recientes no procesadas
        cursor.execute(
            "SELECT TOP 10 ID, date, FK_users, FK_sku, amount "
            "FROM transactions "
            "WHERE ID > ? and result = 'EXITO' or result = 'FRACASO'"
            "ORDER BY ID ASC",
            last_id
        )
        rows = cursor.fetchall()

        for row in rows:
            data = {
                "ID": row.ID,
                "date": str(row.date),
                "FK_users": row.FK_users,
                "FK_sku": row.FK_sku,
                "amount": float(row.amount)
            }
            
            publisher.publish(topic_path, json.dumps(data).encode("utf-8"))
            print(f'Publicado ID = {row.ID}')
            last_id = max(last_id, row.ID)
            pending_ids.discard(row.ID)
        
        #Revalidar transacciones previamente 'en proceso'
        for pid in list(pending_ids):
            cursor.execute("SELECT ID, date, FK_users, FK_sku, amount, status FROM transactions WHERE ID = ?", pid)
            row = cursor.fetchone()
            if row and row.status == 'EXITO':
                data = {
                "ID": row.ID,
                "date": str(row.date),
                "FK_users": row.FK_users,
                "FK_sku": row.FK_sku,
                "amount": float(row.amount)
            }
            
            publisher.publish(topic_path, json.dumps(data).encode("utf-8"))
            print(f'Reprocesando ID = {row.ID}')
            pending_ids.remove(row.ID)
        
        #Identificar transacciones en proceso y agregarlas al conjunto pendiente
        cursor.execute(
            """
            SELECT ID FROM transactions
            WHERE ID > ? AND status = 'en proceso'
            ORDER BY ID ASC
            """,
            last_id
        )

        for row in cursor.fetchall():
            pending_ids.add(row.ID)
                
        time.sleep(10)
        
    except Exception as e:
        print(f"Error encontrado: {str(e)}")
        time.sleep(30)
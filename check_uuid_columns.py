"""
检查所有表的UUID主键列名
"""
from database.db_connection import DatabaseConnection

tables = [
    'doctor_time_slots',
    'doctor_working_schedule',
    'biomechanics_scan',
    'chat_message',
    'prescription_detail'
]

db = DatabaseConnection()

for table in tables:
    try:
        cols = db.execute_query(f'DESCRIBE {table}')
        uuids = [c['Field'] for c in cols if 'UUID' in c['Field'] and c['Key'] == 'PRI']
        print(f'{table}: {uuids}')
    except Exception as e:
        print(f'{table}: ERROR - {e}')

db.close()

from pyexpat import model
from flask import Flask, jsonify, request
import os
import pickle
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error
from sklearn.linear_model import Lasso
import pickle
import os
import sqlite3
from pmdarima.arima import auto_arima
from sklearn.metrics import mean_absolute_error, mean_absolute_percentage_error


os.chdir(os.path.dirname(__file__))
app = Flask(__name__)
app.config['DEBUG'] = True

users = pd.read_csv('data/users_web.csv')





def modification_data(data):
    """Modificar dataFrame ingresado, agregar columnas de day, month, year, cambiar Formato columna Date
    
    Argumentos:
        - df (DataFrame) : DataFrame a tranformar
        
    Retorno:
        - df (DataFrame)
    """
    data[['day', 'month', 'year']] = data['Date'].str.split('/', expand=True)
    data['year'] = data['year'].astype(int)
    data['month'] = data['month'].astype(int)
    data['day'] = data['day'].astype(int)
    data['Date'] = pd.to_datetime(data[['day', 'month', 'year']]).astype(str)
    return data 

def predicciones(periodo):
    """Calcular predicciones, modelo Autoarima
    
    Argumentos:
        - periodo (str) : Input ingresador por el usuario
            
    Retorno:
        -  predicciones (np.array)
    """

    periodo = int(periodo)

    if periodo in [7,28,29,30,31]:
        model = pickle.load(open('data/model.pkl','rb'))
        predicciones = model.predict(periodo)
        inversed_predicciones = np.expm1(predicciones)
        return np.round(inversed_predicciones, 0)

    else:
        return ("Input incorrecto, vete a tu casa")


def predicciones(periodo):

    periodo = int(periodo)

    if periodo in [7,28,29,30,31]:
        model = pickle.load(open('data/model.pkl','rb'))
        predicciones = model.predict(periodo)
        inversed_predicciones = np.expm1(predicciones)
        print(model)
        return np.round(inversed_predicciones, 0)
        
    else:
        return ("Input incorrecto, vete a tu casa") 



def retrain ():
    """Reentrenar modelo, modelo AutoArima
    
    Retorno:
        -  (string) | MAPE
    """
    connection = sqlite3.connect('data/users_thebridge.db')
    cursor = connection.cursor()
    data = "SELECT * FROM USERS" #query
    result = cursor.execute(data).fetchall()
    names = [description[0] for description in cursor.description]
    connection.close()
    df = pd.DataFrame(result,columns=names)
    
    model = pickle.load(open('data/model.pkl','rb'))
          
    df['Users'] = np.log1p(df['Users'])
   
    numero_observaciones_totales = model.nobs_ + 30
    numero_dias_add = len(df) - numero_observaciones_totales     
    print(numero_dias_add)
    if numero_dias_add > 29:  
        test = df['Users'][-30:]
        
        prediciones = model.predict(len(test))
        nuevo_mape =  mean_absolute_percentage_error(test.values, prediciones)
    
        if nuevo_mape > 0.20:
            
            train = df['Users'][:-30]
            test = df['Users'][-30:]
            
            model = auto_arima(
            train,
            start_p=1,
            start_q=1,
            max_d=3,
            max_p=5,
            max_q=5,
            stationary=False, 
            random_state=42,
            trace=True,
            n_fits = 50
            )
            prediciones = model.predict(len(test))     
            nuevo_mape_retrain =  mean_absolute_percentage_error(test.values, prediciones)
            pickle.dump(model, open('data/model.pkl', 'wb'))
            print(f"El modelo se reentreno debido a que la métrica MAPE, {np.round(nuevo_mape*100, 0)}, es mayor del 20%.")
            return nuevo_mape_retrain

        else:
            print(f"No es necesario reentrenar el modelo, ya que el MAPE, {np.round(nuevo_mape*100, 0)}, no es mayor del 20%.")
            return nuevo_mape
    else:
        return f"Sin datos suficientes {numero_dias_add} registro(s). Tienen que existir 30 registros (1 mes) nuevos en la base de datos para reentrenar el modelo" 



def create_db_csv(data):
    """Crear base da datos, e ingresar los registros del DataFrame a la base de datos creada
    
    Argumentos:
        - df (DataFrame) : DataFrame a tranformar
        
    Retorno:
        -  (string)
    """
    modification_data(data)
    connection = sqlite3.connect("data/users_thebridge.db")
    crsr = connection.cursor()
    
    create_table = """
    CREATE TABLE USERS (
    Date DATE,
    Users int(5),
    day int(5),
    month int(5),
    year int(5)
    );
    """
    eliminate_table = """
        DROP TABLE USERS;
        """
    try:        
        crsr.execute(create_table)
    except:        
        crsr.execute(eliminate_table)
        crsr.execute(create_table)
        
    for index, row in data.iterrows():
        crsr.execute("""INSERT INTO USERS (Date, Users, day, month, year) values(?,?,?,?,?)""", (row.Date, row.Users, row.day, row.month, row.year))
    
    connection.commit()
    connection.close()
    return "Base de Datos Creada"

"""
----------------------------------------------------------------------------------------------------------------------------------------------------------------------------
"""

users1 = users.to_json()        

@app.route('/', methods=['GET'])
def home():
    create_db_csv(users)
    return "Api trabajo"


@app.route('/v1/prediction', methods=['GET'])
def prediction():  

    periodo = int(request.args.get('periodo', None))
    
    if periodo is None :
        return "Args empty, the data are not enough to predict"
    else:
        final = predicciones(periodo)
        
        if type(final) == str:
            return final 
        else: 
            return jsonify({'predictions': final.sum()})


#http://127.0.0.1:5000/v1/prediction?periodo=7

@app.route('/v1/retrain', methods=['PUT'])
def retraining():

    return retrain()

#http://127.0.0.1:5000/v1/retrain

app.run()



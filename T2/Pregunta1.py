#from gurobipy import *
import gurobipy as gp
import numpy as np
from gurobipy import GRB

# Se entrega esta funcion a la cual dandole los patrones y los costos por pieza, calcula el costo por patron
def costos_camino(camino, costos):
    suma = []
    for i in range(len(camino)):
        sumita = 0
        for j in range(len(camino[i])):
            sumita += camino[i][j] * costos[j]
        if sumita >= 0:
            suma = suma + [sumita]
    return suma

def resolver_problema_generacion_columnas(tamano_items, tamano_materia_prima, costos, gamma, demanda, error):
    """Funcion que ejecuta el algoritmo"""

    # 1º Se crean patrones de corte iniciales ineficientes ( recordar que
    # no importa la solucion inicial, es sólo para partir). Los patrones están
    # basados en cuántas piezas de un tipo caben
    
    NITER = 10
    iteracion = 0
    
    patron = []
    m = len(tamano_items)

    for i, tamano in enumerate(tamano_items):
        pat = [0]*m
        pat[i] = int(tamano_materia_prima/tamano)
        patron.append(pat)



    K = len(patron)
    costos_patrones = costos_patron(patron, costos)


    # calcular costos patrones 
    
    # 2º Se genera el objeto y variables necesarias para el 
    # Problema Maestro
    maestro = gp.Model("Problema maestro")
    
    # 2.1º Se crea un diccionario donde la llave es el subindice de la variable X
    # y el valor es la variable de gurobi
    x = {}
    for k in range(K):
        x[k] = maestro.addVar(lb=0, name="x[%d]"%k)
    maestro.update()
    maestro.Params.OutputFlag = 0

    # 2.2º Se crea un diccionario con las restricciones donde la llave es el subindice de
    # la restriccion de demanda asociada
    ordenes={}
    for i in range(m):
        ordenes[i] = maestro.addConstr(sum(patron[k][i]*x[k] for k in range(K)) >= demanda[i], name="Orden de demanda[%d]"%i)
    maestro.update()
    
    #2.3 Se crea la función objetivo del maestro
    maestro.setObjective(sum(x[k]*(gamma + costos_patrones[k]) for k in range(K)),GRB.MINIMIZE)
    maestro.update()
    
    #2.4 Se define el problema satélite
    satelite = gp.Model("Satelite")
    y = {}
    for i in range(m):
        y[i] = satelite.addVar(lb=0, vtype=GRB.INTEGER, name="y[%d]"%i)
    satelite.update()
    
    # 2.5 Se agrega la restriccion de capacidad asociada al satelite
    satelite.addConstr(sum(tamano_items[i]*y[i] for i in range(m)) <= tamano_materia_prima, name="Tamaño materia prima")
    satelite.update()
    
    # 2.6 Se agrega la función objetivo del satelite. Inicialmente se define
    # con coeficientes ficticios en la función objetivo, estos cambiarán en
    # las iteraciones.
    pi = [1]*m
    satelite.setObjective(sum((costos[i] - pi[i]) * y[i] for i in range(m)),GRB.MINIMIZE)
    satelite.update()

    # 3º Comienza el algoritmo
    while (iteracion < NITER) :
        # 3.1º Se optimiza el problema maestro relajado
        iteracion = iteracion + 1
        print("\n\nIteración:", iteracion)
        maestro_relajado = maestro.relax()
        maestro_relajado.optimize()
        print("Objetivo del maestro relajado:", maestro_relajado.ObjVal)
    
        # 3.2ª Se almacenan las variables duales para luego ser ocupadas
        # en el subproblema y se define este problema, cabe recordar que es un
        # problema de tipo knapsack y este se maximiza.
        
        pi = [c.Pi for c in maestro_relajado.getConstrs()]

        # 3.5º Se resuelve el subproblema, se actualiza la función objetivo antes
        satelite.Params.OutputFlag = 0
        satelite.setObjective(sum((costos[i] - pi[i]) * y[i] for i in range(m)),GRB.MINIMIZE)
        satelite.update()
        satelite.optimize()

        print("Objetivo del satélite:", satelite.ObjVal)

        # 3.6º Se termina el problema si se cumple el criterio de parada
        if satelite.ObjVal + gamma >= -error: # break if no more columns
            break

        # 3.7º En caso contrario, se generan un nuevo patron de corte y se 
        # agrega a la lista de patrones

        pat = [int(y[i].X) for i in range(m)]
        patron.append(pat)

        #Se añaden nuevos costos
        costos_patrones = costos_patron(patron, costos)
        print("Nuevo costo", costos_patrones[-1])

        print ("Precios sombra y nuevo patrón:")
        for i,d in enumerate(pi):
            print ("\t%5d%12g%7d" % (i,d,pat[i]))
        


        # 3.8º Se agrega la nueva columna al problema maestro
        # primero se define un objeto "columna" y se ponen ahí los 
        # datos del nuevo patrón a agregar.
        col = gp.Column()
        for i in range(m):
            if patron[K][i] > 0:
                col.addTerms(patron[K][i], ordenes[i])

        # 3.9º Ahora se agregar la nueva variable, indicando los 
        # coeficientes de la columna y también el de la función objetivo
        x[K] = maestro.addVar(obj=costos_patrones[K] + gamma, vtype=GRB.INTEGER, name="x[%d]"%K, column=col)
        maestro.update()

        K = K + 1
        print("Fin de la iteración")
        
        
    print("Fin de la generacion de columnas")

    # 4º Se resueve el maestro nuevamente, con todos los patrones generados
    # pero como problema entero
    # Primero hay que cambiar los tipos de las variables a "enteros"
    for var in maestro.getVars():
        var.vtype=GRB.INTEGER

    maestro.optimize()
    print("\n\n Valor objetivo final del problema:", maestro.ObjVal)
    print("Patrones:")
    for k in x:
        if x[k].X > error:
            print ("Patron:", k,)
            print ("\tTamaños:",)
            print ([tamano_items[i] for i in range(m) if patron[k][i]>0 for j in range(patron[k][i])],)
            print ("--> %d Rollos" % int(x[k].X+.5))

    # 5º Retornamos los rollos de materia cortados (Lo esperado del problema)
    rollos = []
    for k in x:
        for j in range(int(x[k].X)):
            rollos.append(sorted([tamano_items[i] for i in range(m) if patron[k][i]>0 for j in range(patron[k][i])]))
    rollos.sort()
    return rollos


if __name__ == '__main__':

    # El programa principal define los datos básicos.
    # Aquí están los del ejemplo de clases.
    
    tamano_items = [20,45,50,55,75]
    demanda = [48,35,24,10,8]

    # definir costos y gamma (que la funcion debe recibir)
    costos = [3, 10, 8, 11, 15]
    #costos = [0]*5
    gamma = 5
    #gamma = 1

    # Valores que se pueden modificar
    tamano_materia_prima = 110
    error = 1.e-6
    
    rollos = resolver_problema_generacion_columnas(tamano_items, tamano_materia_prima, costos, gamma, demanda, error)

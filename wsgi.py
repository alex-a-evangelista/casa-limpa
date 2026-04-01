"""Arquivo de entrada para PythonAnywhere"""
import os
import sys

# Caminho do projeto no PythonAnywhere
project_home = os.path.dirname(os.path.abspath(__file__))
if project_home not in sys.path:
    sys.path.insert(0, project_home)

from server import app as application, init_db

# Inicializar banco de dados
init_db()

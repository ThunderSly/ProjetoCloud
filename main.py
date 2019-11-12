#!/usr/bin/env python3

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

contadorId = 0

Dict = {}

class Tarefa(BaseModel):
    nome: str

class Tarefas:
    def __init__(self, nome):
        global contadorId
        self.id = contadorId
        self.nome = nome
        Dict[contadorId] = nome
        contadorId += 1

@app.get("/Tarefa/")
async def listar():
    return list(Dict.values())

@app.post("/Tarefa/")
async def add(tarefa: Tarefa):
    tarefa_dict = tarefa.dict()
    Tarefa1 = Tarefas(tarefa_dict["nome"])
    return

@app.get("/Tarefa/{id}")
async def show(id: int):
    return Dict.get(id)

@app.put("/Tarefa/{id}")
async def update(id: int, tarefa: Tarefa):
    tarefa_dict = tarefa.dict()
    Dict[id] = tarefa_dict["nome"]
    return

@app.delete("/Tarefa/{id}")
async def delete(id: int):
    del Dict[id]
    return 

@app.get("/healthcheck/")
async def check():
    return 


# ProjetoCloud
### Servidor de Cloud Hibrido

Instalar boto3 e awscli via pip:
```
$ pip3 install boto3
$ pip3 install awscli --upgrade --user
```
Configurar AWS utilizando as Chaves de acesso:
```
$ aws configure
```
Rodar o programa principal:
```
$ python3 projetoBrubs.py
```

Esperar programa terminar e obter o DNS do seu LoadBalancer. Entrar com esse URL no seu browser de escolha:
```
http://<LOADBALANCERDNS>:5000/docs
```

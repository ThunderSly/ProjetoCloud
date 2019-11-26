import time
import boto3
from botocore.exceptions import ClientError
import os

virginiaClient = boto3.client('ec2', region_name='us-east-1')
virginiaEc2 = boto3.resource('ec2', region_name='us-east-1')
virginiaElbv2 = boto3.client('elbv2', region_name='us-east-1')
virginiaAutoScale = boto3.client('autoscaling', region_name='us-east-1')

ohioClient = boto3.client('ec2', region_name='us-east-2')
ohioEc2 = boto3.resource('ec2', region_name='us-east-2')

def keypairCreate(name, client):
    response = client.create_key_pair(KeyName=name)
    if(os.path.exists('{}'.format(name)+'.pem')):
        os.remove('{}'.format(name)+'.pem')
    response_file = open('{}'.format(name)+'.pem','w+')
    response_file.write(response['KeyMaterial'])
    response_file.close()
    print("Key Pair Generated")
    os.chmod('{}'.format(name)+'.pem', 0o400)

def keypairDelete(name, client):
    try:
        response = client.describe_key_pairs(KeyNames=[name])
        client.delete_key_pair(KeyName=name)
        print("Key Pair Deleted")
    except ClientError as e:
        print(e)

def secgroupRedirectCreate(name, client):
    data = client.describe_vpcs()
    vpcID = data.get('Vpcs', [{}])[0].get('VpcId', '')
    try:
        data = client.create_security_group(GroupName=name,Description='SecGroup Brubs',VpcId=vpcID)
        secGroupID = data['GroupId']
        print('Security Group Generated')
        response = client.authorize_security_group_ingress(
            GroupId=secGroupID,
            IpPermissions=[
                {'IpProtocol': 'tcp',
                    'FromPort': 22,
                    'ToPort': 22,
                    'IpRanges': [{'CidrIp': '0.0.0.0/0'}]},
                {'IpProtocol': 'tcp',
                    'FromPort': 5000,
                    'ToPort': 5000,
                    'IpRanges': [{'CidrIp': '0.0.0.0/0'}]}
            ]
        )
        print('Ingress Set')
        return secGroupID

    except ClientError as e:
        print(e)

def secgroupMongoCreate(name):
    data = ohioClient.describe_vpcs()
    vpcID = data.get('Vpcs', [{}])[0].get('VpcId', '')
    try:
        data = ohioClient.create_security_group(GroupName=name, Description="Sec Group Brubs Mongo", VpcId = vpcID)
        secGroupID = data['GroupId']
        print('Security Group Generated')
        response = ohioClient.authorize_security_group_ingress(
            GroupId=secGroupID,
            IpPermissions=[
                {
                    'IpProtocol' : 'tcp',
                    'FromPort' : 22,
                    'ToPort' : 22,
                    'IpRanges' : [{'CidrIp' : '0.0.0.0/0'}]
                },
                {
                    'IpProtocol' : 'tcp',
                    'FromPort' : 27017,
                    'ToPort' : 27017,
                    'IpRanges' : [{'CidrIp' : '0.0.0.0/0'}]
                }
            ]
        )
        print('Ingress Set')
        return secGroupID

    except ClientError as e:
        print(e)

def secgroupDelete(name, client):
    try:
        response = client.delete_security_group(GroupName=name)
        print('Security Group Deleted')
    except ClientError as e:
        print(e)

def secgroupIngress(secGroupID, client, ip, port):
    print("Mudando Ingresse dos SecGroups")
    response = client.authorize_security_group_ingress(
        GroupId=secGroupID,
        IpPermissions=[
            {
                'IpProtocol' : 'tcp',
                'FromPort' : 22,
                'ToPort' : 22,
                'IpRanges' : [{'CidrIp' : '0.0.0.0/0'}]
            },
            {
                'IpProtocol' : 'tcp',
                'FromPort' : port,
                'ToPort' : port,
                'IpRanges' : [{'CidrIp' : '{}/32'.format(ip)}]
            }
        ]
    )
    response = client.revoke_security_group_ingress(
        GroupId=secGroupID,
        IpPermissions=[
            {
                'IpProtocol' : 'tcp',
                'FromPort' : port,
                'ToPort' : port,
                'IpRanges' : [{'CidrIp' : '0.0.0.0/0'}]
            }
        ]
    )

def instanceMongo():
    instancesMongo = ohioEc2.create_instances(
        ImageId='ami-0d5d9d301c853a04a',
        MinCount=1,
        MaxCount=1,
        SecurityGroups=['AutoSec-Mongo'],
        KeyName='AutoKey-Mongo',
        InstanceType='t2.micro',
        TagSpecifications=[{'ResourceType': 'instance', 'Tags': [{'Key': 'Owner', 'Value': 'Brubs'}, {'Key': 'Name', 'Value': 'AutoBrubs-Mongo'}]}],
        UserData='''#! /bin/bash
                sudo apt update -y
                sudo apt-get install gnupg
                wget -qO - https://www.mongodb.org/static/pgp/server-4.2.asc | sudo apt-key add -
                echo "deb [ arch=amd64 ] https://repo.mongodb.org/apt/ubuntu bionic/mongodb-org/4.2 multiverse" | sudo tee /etc/apt/sources.list.d/mongodb-org-4.2.list
                sudo apt-get update -y
                sudo apt-get install -y mongodb-org
                echo "mongodb-org hold" | sudo dpkg --set-selections
                echo "mongodb-org-server hold" | sudo dpkg --set-selections
                echo "mongodb-org-shell hold" | sudo dpkg --set-selections
                echo "mongodb-org-mongos hold" | sudo dpkg --set-selections
                echo "mongodb-org-tools hold" | sudo dpkg --set-selections
                sudo service mongod start
                sudo sed -i "s/127.0.0.1/0.0.0.0/g" /etc/mongod.conf
                sudo service mongod restart
                '''
    )
    ids=[]
    print("Mongo Instance Created")
    for i in instancesMongo:
        ids.append(i.id)
    waiter = ohioClient.get_waiter('instance_status_ok')
    waiter.wait(InstanceIds = [ids[0]])
    
    mongoResponse = ohioClient.describe_instances(InstanceIds=[ids[0]])
    print("Instances Running")
    return mongoResponse['Reservations'][0]['Instances'][0]['NetworkInterfaces'][0]['PrivateIpAddresses'][0]['PrivateIpAddress']

def instanceMongoWeb(mongoIP):
    instancesMongo = ohioEc2.create_instances(
        ImageId='ami-0d5d9d301c853a04a',
        MinCount=1,
        MaxCount=1,
        SecurityGroups=['AutoSec-MongoWeb'],
        KeyName='AutoKey-Mongo',
        InstanceType='t2.micro',
        TagSpecifications=[{'ResourceType': 'instance', 'Tags': [{'Key': 'Owner', 'Value': 'Brubs'}, {'Key': 'Name', 'Value': 'AutoBrubs-MongoWeb'}]}],
        UserData='''#! /bin/bash
                    sudo apt update
                    sudo apt install -y python3-pip
                    pip3 install pymongo
                    pip3 install fastapi
                    pip3 install pydantic==0.32.2
                    pip3 install uvicorn
                    pip3 install requests -y
                    cd home/ubuntu
                    git clone https://github.com/ThunderSly/REST-FastAPI.git
                    cd REST-FastAPI
                    export mongoIP={}
                    uvicorn main:app --port 5000 --host 0.0.0.0 --reload &
                    curl 127.0.0.1:8000
                '''.format(mongoIP)
    )
    ids=[]
    print("Mongo Instance Created")
    for i in instancesMongo:
        ids.append(i.id)
    waiter = ohioClient.get_waiter('instance_status_ok')
    waiter.wait(InstanceIds = [ids[0]])
    mongoResponse = ohioClient.describe_instances(InstanceIds=[ids[0]])
    print("Instances Running")
    return mongoResponse['Reservations'][0]['Instances'][0]['PublicIpAddress']

def instanceRedirectWeb(mongoWebIP):
    instancesWeb = virginiaEc2.create_instances(
        ImageId='ami-04b9e92b5572fa0d1',
        MinCount=1,
        MaxCount=1,
        SecurityGroups=["AutoSec"],
        KeyName="AutoKey",
        InstanceType="t2.micro",
        TagSpecifications=[{'ResourceType': 'instance', 'Tags': [{'Key': 'Owner', 'Value': 'Brubs'}, {'Key': 'Name', 'Value': 'AutoBrubs-Redirect'}] }],
        UserData='''#! /bin/bash
                    sudo apt-get update
                    sudo apt-get -y install python3-pip
                    pip3 install fastapi
                    pip3 install pydantic==0.32.2
                    pip3 install uvicorn
                    pip3 install requests -y
                    cd home/ubuntu
                    git clone https://github.com/ThunderSly/REST-FastAPI.git
                    cd REST-FastAPI
                    export redirectIP={}
                    uvicorn redirectIP:app --port 5000 --host 0.0.0.0 --reload &
                    curl 127.0.0.1:8000
                '''.format(mongoWebIP)
    )
    print("Web Instance Created")
    ids = []
    for i in instancesWeb:
        ids.append(i.id)
    waiter = virginiaClient.get_waiter('instance_status_ok')
    waiter.wait(InstanceIds = [ids[0]])
    print("Instance Running")
    webResponse = virginiaClient.describe_instances(InstanceIds=[ids[0]])
    return webResponse['Reservations'][0]['Instances'][0]['PublicIpAddress']

def instanceWebFinal(redirectWebIP):
    instancesWeb = virginiaEc2.create_instances(
        ImageId='ami-04b9e92b5572fa0d1',
        MinCount=1,
        MaxCount=1,
        SecurityGroups=["AutoSec"],
        KeyName="AutoKey",
        InstanceType="t2.micro",
        TagSpecifications=[{'ResourceType': 'instance', 'Tags': [{'Key': 'Owner', 'Value': 'Brubs'}, {'Key': 'Name', 'Value': 'AutoBrubs-Web'}] }],
        UserData='''#! /bin/bash
                    sudo apt-get update
                    sudo apt-get -y install python3-pip
                    pip3 install fastapi
                    pip3 install pydantic==0.32.2
                    pip3 install uvicorn
                    pip3 install requests -y
                    cd home/ubuntu
                    git clone https://github.com/ThunderSly/REST-FastAPI.git
                    cd REST-FastAPI
                    export redirectIP={}
                    uvicorn redirectIP:app --port 5000 --host 0.0.0.0 --reload &
                    curl 127.0.0.1:8000
                '''.format(redirectWebIP)
    )
    print("Web Instance Created")
    ids = []
    for i in instancesWeb:
        ids.append(i.id)
    waiter = virginiaClient.get_waiter('instance_status_ok')
    waiter.wait(InstanceIds = [ids[0]])
    print("Instance Running")
    webResponse = virginiaClient.describe_instances(InstanceIds=[ids[0]])
    return [webResponse['Reservations'][0]['Instances'][0]['PublicIpAddress'], ids[0]]

def instancesDelete(ec2R, client):
    try:
        data = client.describe_instances(Filters=[{'Name': 'tag:Owner','Values': ['Brubs']}])
        instanceIds = []
        for i in data["Reservations"]:
            instanceIds.append(i["Instances"][0]["InstanceId"])
        for i in instanceIds:
            ec2R.instances.filter(InstanceIds=[i]).terminate()
        print("Waiting...")
        waiter = client.get_waiter('instance_terminated')
        waiter.wait(Filters = [{'Name':'tag:Owner','Values': ['Brubs']}])
        print("Instances Deleted")

    except ClientError as e:
        print(e)

def loadBalancerDelete(name):
    try:
        lbARN = virginiaElbv2.describe_load_balancers(Names=[name])["LoadBalancers"][0]['LoadBalancerArn']
        waiter = virginiaElbv2.get_waiter('load_balancers_deleted')
        virginiaElbv2.delete_load_balancer(LoadBalancerArn=lbARN)
        print("Waiting...")
        waiter.wait(LoadBalancerArns=[lbARN])
        print("Load Balancer Deleted")

    except ClientError as e:
        print(e)

def loadBalancerCreate(name, secGroupID):
    response = virginiaElbv2.create_load_balancer(
        Name=name,
        Subnets=[
        'subnet-65c07202',
        'subnet-782d9356',
        'subnet-dfc28195',
        'subnet-7c55e920',
        'subnet-6f905151',
        'subnet-a69ee8a9'
        ],
        Type = 'application',
        SecurityGroups=[secGroupID],
        Tags=[{'Key': 'Owner','Value': 'Brubs'}]
    )
    print("Waiting...")
    lbARN = response['LoadBalancers'][0]['LoadBalancerArn']
    waiter = virginiaElbv2.get_waiter('load_balancer_available')
    waiter.wait(LoadBalancerArns = [lbARN])
    print("Load Balancer OK")
    return lbARN

def imageDelete(name):
    try:
        data = virginiaClient.describe_images(Filters=[{'Name': 'name','Values': [name]}])
        if len(data["Images"]) > 0:
            imageID=(data["Images"][0]['ImageId'])
            virginiaClient.deregister_image(ImageId=imageID)
            print('Image Deleted')
    except ClientError as e:
        print(e)

def imageCreate(instanceID, name):
    data = virginiaClient.create_image(InstanceId=instanceID,Name=name)
    imageID = data['ImageId']
    waiter =virginiaClient.get_waiter('image_available')
    print("Waiting...")
    waiter.wait(ImageIds=[imageID])
    print("Image Generated")
    return imageID

def launchConfigCreate(imageID, name, ip):
    data = virginiaAutoScale.create_launch_configuration(
        LaunchConfigurationName=name,
        ImageId=imageID,
        KeyName='AutoKey',
        SecurityGroups=['AutoSec'],
        InstanceType = 't2.micro',
        InstanceMonitoring={'Enabled': True},
        UserData = '''#!/bin/bash
                    cd home/ubuntu/
                    cd REST-FastAPI
                    export redirectIP={}
                    uvicorn redirectIP:app --reload --host "0.0.0.0" --port 5000
        '''.format(ip)
    )
    print("Launch Configuration Generated")

def launchConfigDelete(name):
    try:
        response = virginiaAutoScale.delete_launch_configuration(LaunchConfigurationName=name)
        print("Launch Configuration Deleted")
    except ClientError as e:
        print(e)

def targetGroupCreate(name):
    data = virginiaClient.describe_vpcs()
    vpcID = data.get('Vpcs', [{}])[0].get('VpcId', '')
    response = virginiaElbv2.create_target_group(
        Name=name,
        Protocol='HTTP',
        Port=5000,
        VpcId=vpcID,
        TargetType='instance',
        HealthCheckEnabled=True
    )
    tgARN = response['TargetGroups'][0]['TargetGroupArn']
    print("Target Group Generated")
    return tgARN

def targetGroupDelete(name):   
    try:
        data = virginiaElbv2.describe_target_groups(Names=[name])
        tgARN = data['TargetGroups'][0]['TargetGroupArn']
        response = virginiaElbv2.delete_target_group(TargetGroupArn=tgARN)
        print("Target Group Deleted")
    except ClientError as e:
        print(e)

def listenerCreate(tgARN, lbARN):
    response = virginiaElbv2.create_listener(LoadBalancerArn = lbARN, Protocol = "HTTP", Port = 5000, DefaultActions = [{"Type":"forward","TargetGroupArn":tgARN}])
    print("Listener Generated")

def autoScalingCreate(name,tgARN):
    response = virginiaAutoScale.create_auto_scaling_group(
    AutoScalingGroupName=name,
    LaunchConfigurationName='AutoLaunch',
    DefaultCooldown=50,
    MinSize=1,
    HealthCheckGracePeriod=300,
    MaxSize=3,
    DesiredCapacity=1,
    TargetGroupARNs=[tgARN],
    AvailabilityZones=[
            'us-east-1a',
            'us-east-1b',
            'us-east-1c',
            'us-east-1d',
            'us-east-1e',
            'us-east-1f'
    ],
    Tags=[{'Key': 'tag:Owner','Value': 'Brubs'}]
    )
    print("Auto Scaling Generated")

def autoScalingDelete(name):
    try:
        response = virginiaAutoScale.delete_auto_scaling_group(AutoScalingGroupName=name, ForceDelete = True)
        print("Waiting...")
        while True:
            check = virginiaAutoScale.describe_auto_scaling_groups(AutoScalingGroupNames=[name])
            tamanho = len(check['AutoScalingGroups'])
            if tamanho == 0:
                break
            time.sleep(3)
        print("AutoScale Deleted")
    except ClientError as e:
        print(e)

autoScalingDelete("AutoScaleBrubs")
instancesDelete(virginiaEc2, virginiaClient)
instancesDelete(ohioEc2, ohioClient)

loadBalancerDelete("AutoLoad-Brubs")
time.sleep(25)
launchConfigDelete('AutoLaunch')
imageDelete('AutoImage')
targetGroupDelete('AutoTarget-Brubs')

keypairDelete("AutoKey", virginiaClient)
keypairDelete("AutoKey-Mongo", ohioClient)

secgroupDelete("AutoSec", virginiaClient)
secgroupDelete('AutoSec-Mongo', ohioClient)
secgroupDelete('AutoSec-MongoWeb', ohioClient)
secgroupDelete('AutoSec-Empty1', ohioClient)
secgroupDelete('AutoSec-Empty2', ohioClient)

keypairCreate("AutoKey", virginiaClient)
keypairCreate("AutoKey-Mongo", ohioClient)

secGroupIDWeb = secgroupRedirectCreate("AutoSec", virginiaClient)
secGroupIDMongoWeb = secgroupRedirectCreate("AutoSec-MongoWeb", ohioClient)
secGroupIDMongo = secgroupMongoCreate("AutoSec-Mongo")

lbARN = loadBalancerCreate("AutoLoad-Brubs", secGroupIDWeb)

ipMongo = instanceMongo()
ipMongoWeb = instanceMongoWeb(ipMongo)
# secgroupIngress(secGroupIDMongo, ohioClient, ipMongoWeb, 27017)
ipRedirectWeb = instanceRedirectWeb(ipMongoWeb)
# secgroupIngress(secGroupIDMongoWeb, ohioClient, ipRedirectWeb, 5000)
data = instanceWebFinal(ipRedirectWeb)

imageID = imageCreate(data[1], 'AutoImage')
launchConfigCreate(imageID, "AutoLaunch", ipRedirectWeb)
tgARN = targetGroupCreate("AutoTarget-Brubs")
listenerCreate(tgARN, lbARN)
autoScalingCreate("AutoScaleBrubs", tgARN)




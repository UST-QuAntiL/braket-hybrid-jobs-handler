from distutils.command.config import config
from distutils.file_util import copy_file
import threading
import base64
import zipfile
from tempfile import mkdtemp
import boto3
from botocore.config import Config
import requests
from urllib.request import urlopen
import os
import random
import string
import json
import tarfile

def poll():
    print('Polling for new external tasks at the Camunda engine with URL: ', pollingEndpoint)

    body = {
        "workerId": "$ServiceNamePlaceholder",
        "maxTasks": 1,
        "topics":
            [{"topicName": topic,
              "lockDuration": 100000000
              }]
    }

    try:
        response = requests.post(pollingEndpoint + '/fetchAndLock', json=body)

        if response.status_code == 200:
            for externalTask in response.json():
                print('External task with ID for topic ' + str(externalTask.get('topicName')) + ': '
                      + str(externalTask.get('id')))
                variables = externalTask.get('variables')
                if externalTask.get('topicName') == topic:
                    # load input data
                    my_config = Config(
                        region_name = 'us-east-1',
                    )
                    access_key = variables.get('access_key').get('value')
                    access_key = str(access_key).lstrip().rstrip()
                    secret_access_key = variables.get('secret_access_key').get('value')
                    secret_access_key = str(secret_access_key).lstrip().rstrip()
                    device = variables.get('device').get('value')
                    bucket_name = variables.get('bucket').get('value')
                    role_Arn = variables.get('roleArn').get('value')
                    ##### CREATE HYBRID JOB
                    # deploy the related Amazon Braket Hybrid Jobs program on service startup
                    directory_to_extract_to = mkdtemp()
                    with zipfile.ZipFile('hybrid_program.zip', 'r') as zip_ref:
                        zip_ref.extractall(directory_to_extract_to)
                    hybridProgrammTar = os.path.join(os.getcwd(), os.path.join(directory_to_extract_to, "hybrid-jobs.tar.gz"))
                    s3client = boto3.client('s3', aws_access_key_id=access_key, aws_secret_access_key=secret_access_key, config=my_config)
                    s3client.upload_file(hybridProgrammTar, bucket_name, 'hybrid-jobs.tar.gz')
                
                    random_suffix = ''.join(random.choices(string.ascii_uppercase, k=15))
                    job_name = "HybridJob" + random_suffix
                    ##### LOAD INPUT DATA SECTION

                    program_inputs = {}
                    # create an Amazon Braket Hybrid Job 
                    braketClient = boto3.client('braket', aws_access_key_id=access_key, aws_secret_access_key=secret_access_key, config=my_config)
                    response = braketClient.create_job(
                                    algorithmSpecification={
                                        'containerImage': {
                                            'uri': '292282985366.dkr.ecr.us-east-1.amazonaws.com/amazon-braket-base-jobs:1.0-cpu-py37-ubuntu18.04'
                                        },
                                        'scriptModeConfig': {
                                            'compressionType': 'GZIP',
                                            'entryPoint': 'hybrid_program:main',
                                            's3Uri': 's3://' + bucket_name + '/hybrid-jobs.tar.gz'
                                        }
                                    },
                                    checkpointConfig={
                                        's3Uri': 's3://'+ bucket_name + '/checkpoints/'
                                    },
                                    deviceConfig={
                                        'device': device
                                    },
                                    hyperParameters=program_inputs,
                                    inputDataConfig=[],
                                    instanceConfig= {
                                        'instanceCount': 1,
                                        'instanceType': 'ml.m5.large',
                                        'volumeSizeInGb': 1
                                    },
                                    jobName=job_name,
                                    outputDataConfig={
                                        's3Path': 's3://' + bucket_name + '/jobs/' + job_name + '/'
                                    },
                                    roleArn=role_Arn
                                )
                    response2 = braketClient.get_job(
                            jobArn=response['jobArn']
                      )
                    status = response2['status']
                    print('Status of the created job')
                    print(response2)
                    outputPath = str(response2['outputDataConfig'])
                    # wait until job is completed
                    while status != 'COMPLETED':
                        response2 = braketClient.get_job(
                                jobArn=response['jobArn']
                            )
                        status = response2['status']
                    print('Response message of the completed job')
                    print(response2)
                    outputPath = outputPath.replace("'", '"')
                    outputPath = json.loads(outputPath)
                    folder = 'jobs/' + job_name + '/output'
                    file_name = 'model.tar.gz' 
                    result = download_output_file(s3client, bucket_name, folder, file_name)
                    #print(result)

                    # encode parameters as files due to the string size limitation of camunda
                    ##### STORE OUTPUT DATA SECTION

                    # send response
                    body = {}
                    response = requests.post(pollingEndpoint + '/' + externalTask.get('id') + '/complete', json=body)
                    print('Status code of response message: ' + str(response.status_code))

    except Exception:
        print('Exception during polling!')

    threading.Timer(8, poll).start()

def download_data(url):
    response = urlopen(url)
    data = response.read().decode('utf-8')
    return str(data)

def download_output_file(s3_client, bucket, folder, file_name):
    result = ""
    key = folder + "/" + file_name
    directory_to_extract = mkdtemp() + os.sep
    print(directory_to_extract)
    with open(directory_to_extract + file_name, 'wb') as f:
       s3_client.download_fileobj(bucket, key, f)

    if file_name.endswith("tar.gz"):
        tar = tarfile.open(directory_to_extract + os.sep + file_name, "r:gz")
        tar.extractall(directory_to_extract)
        hybrid_program_data = os.path.join(os.getcwd(), os.path.join(directory_to_extract, "results.json"))
        print(hybrid_program_data)
        with open(hybrid_program_data, 'r') as myfile:
            data = myfile.read()
            obj = json.loads(data)
            job_results = str(obj['dataDictionary']).replace("'", '"')
            result = json.loads(job_results)
        tar.close()
    
    return result

# start polling for requests
camundaEndpoint = os.environ['CAMUNDA_ENDPOINT']
pollingEndpoint = camundaEndpoint + '/external-task'
topic = os.environ['CAMUNDA_TOPIC']
poll()

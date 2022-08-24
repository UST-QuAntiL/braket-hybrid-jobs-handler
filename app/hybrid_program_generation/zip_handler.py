# ******************************************************************************
#  Copyright (c) 2022 University of Stuttgart
#
#  See the NOTICE file(s) distributed with this work for additional
#  information regarding copyright ownership.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
# ******************************************************************************

from os import listdir, rename, replace
from tempfile import mkdtemp
from xxlimited import new

from app import app
import zipfile
import os
import tarfile
import os.path

def search_python_file(directory):
    # only .py are supported, also nested in zip files
    containedPythonFiles = [f for f in listdir(os.path.join(directory)) if f.endswith('.py')]
    if len(containedPythonFiles) >= 1:
        app.logger.info('Found Python file with name: ' + str(containedPythonFiles[0]))

        # we only support one file, in case there are multiple files, try the first one
        return os.path.join(directory, containedPythonFiles[0])

    # check if there are nested Python files
    containedZipFiles = [f for f in listdir(os.path.join(directory)) if f.endswith('.zip')]
    for zip in containedZipFiles:

        # extract the zip file
        with zipfile.ZipFile(os.path.join(directory, zip), "r") as zip_ref:
            folder = mkdtemp()
            app.logger.info('Extracting to directory: ' + str(folder))
            zip_ref.extractall(folder)

            # recursively search within zip
            result = search_python_file(folder)

            # return if we found the first Python file
            if result is not None:
                return os.path.join(folder, result)

    return None


def zip_runtime_program(hybridProgramTemp, metaDataTemp):
    app.logger.info('Parameter in zip_runtime_programm')
    if os.path.exists('../hybrid_program.zip'):
        os.remove('../hybrid_program.zip')
    zipObj = zipfile.ZipFile('../hybrid_program.zip', 'w')
    zipObj.write(hybridProgramTemp.name, 'hybrid_program.py')
    zipObj.write(metaDataTemp.name, 'hybrid_program.json')
    # we upload later a file to s3 (which contains the hybrid program) but according to the api documentation it has to be a tar.gz file
    # see https://amazon-braket-sdk-python.readthedocs.io/en/latest/_apidoc/braket.aws.aws_quantum_job.html for more information
    make_tarfile('hybrid-jobs.tar.gz', hybridProgramTemp.name, metaDataTemp.name)
    zipObj.write('/hybrid-jobs.tar.gz')
    zipObj.close()
    zipObj = open('../hybrid_program.zip', "rb")
    return zipObj.read(), '../hybrid_program.zip'

def make_tarfile(output_filename, hybridProgramTemp, metaDataTemp):
    with tarfile.open(output_filename, "w:gz") as tar:
        new_file_location = rename_file(hybridProgramTemp, 'hybrid_program.py')
        tar.add(new_file_location, arcname=os.path.basename('hybrid_program.py'))
        new_file_location = rename_file(metaDataTemp, 'hybrid_program.json')
        tar.add(new_file_location, arcname=os.path.basename('hybrid_program.json'))

def rename_file(path, new_file_name):
    # files have to be renamed since we have to define the 'entryPoint' for the hybrid job execution 
    # otherwise we would have in the tar.gz file random temp names where we have to find the names out
    file_to_rename = os.path.basename(path)
    file_to_rename_location = str(path)
    new_file_location = file_to_rename_location.replace(file_to_rename, new_file_name)
    os.rename(path, new_file_location)
    return new_file_location

def zip_polling_agent(templatesDirectory, pollingAgentTemp, hybridProgram):
    # zip generated polling agent, afterwards zip resulting file with required Dockerfile
    if os.path.exists('../polling_agent.zip'):
        os.remove('../polling_agent.zip')
    if os.path.exists('../polling_agent_wrapper.zip'):
        os.remove('../polling_agent_wrapper.zip')
    zipObj = zipfile.ZipFile('../polling_agent.zip', 'w')
    zipObj.write(pollingAgentTemp.name, 'polling_agent.py')
    zipObj.write(hybridProgram, 'hybrid_program.zip')
    zipObj.close()
    zipObj = zipfile.ZipFile('../polling_agent_wrapper.zip', 'w')
    zipObj.write('../polling_agent.zip', 'service.zip')
    zipObj.write(os.path.join(templatesDirectory, 'Dockerfile'), 'Dockerfile')
    zipObj = open('../polling_agent_wrapper.zip', "rb")
    return zipObj.read()

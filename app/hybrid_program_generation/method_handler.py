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

import random

from app import app


def add_method_recursively(hybridProgramBaron, taskFile, methodNode, prefix):
    """Add the given method node and all dependent methods, i.e., called methods to the given RedBaron object."""
    app.logger.info('Recursively adding methods. Current method name: ' + methodNode.name)

    # get assignment nodes and check if they call local methods
    assignmentNodes = methodNode.find_all('assignment', recursive=True)

    # iterate over all assignment nodes and check if they rely on a local method call
    for assignmentNode in assignmentNodes:
        # we assume local calls always provide only one name node
        # be careful if you have assignments like this foo = 2 * bar(), the function bar() will not be added, 
        # so you have to provide in the original program two statements: foo = bar() , foo = foo * 2
        assignmentValues = assignmentNode.value
        if str(assignmentValues).__contains__('AwsDevice'):
            assignmentValues = "deviceName = os.environ['SM_HP_DEVICE'] \n device = AwsDevice(deviceName)"
            continue
        if len(assignmentValues) < 2 or str(assignmentValues.value[1].type) != 'call':
            continue

        # extract the name of the local method that is called
        calledMethodNameNode = assignmentValues.value[0]
        
        # check if the method was already added to the RedBaron object
        if len(hybridProgramBaron.find_all('def', name=prefix + '_' + calledMethodNameNode.value)):
            calledMethodNameNode.value = prefix + '_' + calledMethodNameNode.value
            continue

        # filter native primitives that are referenced
        if is_native_reference(calledMethodNameNode.value):
            continue

        # check if the method was imported explicitly
        imported = False
        for importNode in taskFile.find_all('FromImportNode'):
            if len(importNode.targets.find_all('name_as_name', value=calledMethodNameNode.value)) > 0:
                imported = True
        if imported:
            continue

        # find method node in the current file
        recursiveMethodNode = taskFile.find('def', name=calledMethodNameNode.value)
        if not recursiveMethodNode:
            raise Exception('Unable to find method in program that is referenced: ' + calledMethodNameNode.value)

        # update invocation with new method name
        app.logger.info('Found new method invocation of local method: ' + calledMethodNameNode.value)
        addedMethodName, inputParameterList, signatureExtended, backendSignaturePositionsNew = add_method_recursively(
            hybridProgramBaron,
            taskFile,
            recursiveMethodNode,
            prefix)
        calledMethodNameNode.value = addedMethodName

        # handle backend objects in called method
        if backendSignaturePositionsNew:
            app.logger.info('Added method defined backend as parameter at positions: ' + str(backendSignaturePositionsNew))

    # add prefix for corresponding file to the method name to avoid name clashes when merging multiple files
    methodNode.name = prefix + '_' + methodNode.name

    # determine input parameters of the method
    inputParameterList = []
    inputParameterNodes = methodNode.arguments.find_all('def_argument')
    for inputParameterNode in inputParameterNodes:
        inputParameterList.append(inputParameterNode.target.value)

    # add the method to the given RedBaron object
    hybridProgramBaron.append('\n')
    hybridProgramBaron.append(methodNode)
    return methodNode.name, inputParameterList, False, []

def get_unused_method_parameter(prefix, methodNode):
    """Get a variable name that was not already used in the given method using the given prefix"""
    name = prefix
    while True:
        if methodNode.arguments.find('def_argument', target=lambda target: target and (target.value == name)) \
                or check_if_variable_used(methodNode, name):
            name = name + str(random.randint(0, 9))
        else:
            return name


def check_if_variable_used(methodNode, name):
    """Check if a variable with the given name is assigned in the given method"""
    for assignment in methodNode.find_all('assignment'):

        # if assignment has name node on the left side, compare the name of the variable with the given name
        if assignment.target.type == 'name' and assignment.target.value == name:
            return True

        # if assignment has tuple node on the left, check each entry
        if assignment.target.type == 'tuple' and assignment.target.find('name', value=name):
            return True

    return False


def get_output_parameters_of_execute(taskFile):
    """Get the set of output parameters of an execute method within a program"""

    # get the invocation of the execute method to extract the output parameters
    invokeExecuteNode = taskFile.find('assign', recursive=True,
                                      value=lambda value: value.type == 'atomtrailers'
                                                          and len(value.value) == 2
                                                          and value.value[0].value == 'execute')

    # generation has to be aborted if retrieval of output parameters fails
    if not invokeExecuteNode:
        return None

    # only one output parameter
    if invokeExecuteNode.target.type == 'name':
        return [invokeExecuteNode.target.value]
    else:
        # set of output parameters
        return [parameter.value for parameter in invokeExecuteNode.target.value]


def find_element_with_name(assignmentNodes, type, name):
    """Get the RedBaron object with the given type and name out of the set of given RedBaron objects if available"""
    return assignmentNodes.find(type, target=lambda target: target.type == 'name' and (target.value == name))


def is_native_reference(name):
    """Check if the given name belongs to a natively supported method of Python"""
    return name in ['int', 'str', 'len', 'filter', 'enumerate', 'float', 'list', 'dict', 'pow', 'sum']
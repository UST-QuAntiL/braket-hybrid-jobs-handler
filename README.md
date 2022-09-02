[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

# amazon-braket-hybrid-jobs-handler

This service takes a workflow fragment realizing a hybrid algorithm as input and generates a [Amazon Braket Hybrid Jobs](https://docs.aws.amazon.com/braket/latest/developerguide/braket-jobs.html) program to benefit from speedups and reduced queuing times.
Additionally, an agent is generated which handles the transfer of input/output parameters between the Amazon Braket Hybrid Jobs program and a workflow. The implementation from the [qiskit-runtime-handler](https://github.com/UST-QuAntiL/qiskit-runtime-handler) is adapted but the main difference is how the program is uploaded to AWS and how input/output parameters are handled.

The amazon-braket-hybrid-jobs-handler can be used in conjunction with the [QuantME Transformation Framework](https://github.com/UST-QuAntiL/QuantME-TransformationFramework).
Please have a look at the corresponding [documentation](https://github.com/UST-QuAntiL/QuantME-TransformationFramework/tree/develop/docs/quantme/Analysis-and-Rewrite).
Furthermore, a use case showing the rewrite of quantum workflows using the amazon-braket-hybrid-jobs-handler is available [here](https://github.com/UST-QuAntiL/QuantME-UseCases/tree/master/2022-closer).

## Docker Setup
### Current Situation
* Clone the repository:
```
git clone https://github.com/UST-QuAntiL/amazon-braket-hybrid-jobs-handler.git
```

* Build the local docker image and then start the containers using the [docker-compose file](docker-compose.yml): 
```
docker build -t planqk/amazon-braket-hybrid-jobs-handler:local .
docker-compose up

```

### When this repo is added to planqk in dockerhub
* Clone the repository:
```
git clone https://github.com/UST-QuAntiL/amazon-braket-hybrid-jobs-handler.git
```

* Start the containers using the [docker-compose file](docker-compose.yml):
```
docker-compose pull
docker-compose up
```

Now the amazon-braket-hybrid-jobs-handler is available on http://localhost:8890/.

## Local Setup

### Start Redis

Start Redis, e.g., using Docker:

```
docker run -p 5045:5045 redis --port 5045
```

### Configure the Amazon-Braket-Hybrid-Jobs-Handler

Before starting the amazon-braket-hybrid-jobs-handler, define the following environment variables:

```
FLASK_RUN_PORT=8890
REDIS_URL=redis://$DOCKER_ENGINE_IP:5045
```

Thereby, please replace $DOCKER_ENGINE_IP with the actual IP of the Docker engine you started the Redis container.

### Configure the Database

* Install SQLite DB, e.g., as described [here](https://blog.miguelgrinberg.com/post/the-flask-mega-tutorial-part-iv-database)
* Create a `data` folder in the `app` folder
* Setup the results table with the following commands:

```
flask db migrate -m "results table"
flask db upgrade
```

### Start the Application

Start a worker for the request queue:

```
rq worker --url redis://$DOCKER_ENGINE_IP:5045 amazon-braket-hybrid-jobs-handler
```

Finally, start the Flask application, e.g., using PyCharm or the command line.

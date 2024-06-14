#

# Use an official Python runtime as a parent image compatible with ARM architecture
FROM python:3.11.7-slim-bookworm

# Install git
RUN apt-get update && apt-get install -y \
    git \
    gcc \
    libhdf5-dev \
    python3-dev \
    build-essential \
    pkg-config

RUN pip install --upgrade pip
#need to install this separately b/c there is a bug for some reason
# RUN pip install h5py

# Copy the requirements.txt file into the container at /usr/src/app
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir --no-binary=h5py -r requirements.txt

# Set the working directory in the container
WORKDIR /usr/src/app

CMD ["bash"]

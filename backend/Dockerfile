FROM continuumio/miniconda3:latest

LABEL maintainer="Kholy"
LABEL description="Octo VLA environment (JAX; Octo, pinocchio) for finetuning and inference"

WORKDIR /app

COPY environment.yml /tmp/environment.yml

RUN conda env create -f /tmp/environment.yml && \
    conda clean --all --yes

# Install jax with bundled cu12 CUDA libs (matches the cuda12 jaxlib)
RUN /opt/conda/envs/octo/bin/pip install "jax[cuda12]==0.4.26" && \
    /opt/conda/envs/octo/bin/pip install "flax==0.8.2"

RUN git clone https://github.com/kvablack/dlimp.git /opt/dlimp && \
    /opt/conda/envs/octo/bin/pip install -e /opt/dlimp && \
    git clone https://github.com/octo-models/octo.git /opt/octo && \
    /opt/conda/envs/octo/bin/pip install -e /opt/octo && \
    sed -i 's/jax.random.KeyArray/jax.Array/g' /opt/octo/octo/utils/typing.py

ENV PATH=/opt/conda/envs/octo/bin:$PATH
ENV CONDA_DEFAULT_ENV=octo

RUN echo "conda activate octo" >> /root/.bashrc

CMD ["bash"]
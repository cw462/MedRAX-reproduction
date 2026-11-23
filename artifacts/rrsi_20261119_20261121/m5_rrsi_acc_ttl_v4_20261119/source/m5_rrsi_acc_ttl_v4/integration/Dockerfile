FROM continuumio/miniconda3@sha256:1808b31ef43e9c521cde5884ba4df9ec26d8d503a314cea787590f8550358a63

RUN conda create --yes --prefix /opt/m5-native python=3.10.18 pip \
    && /opt/m5-native/bin/python -m pip install --no-cache-dir \
       numpy==1.26.0 scipy==1.11.4 scikit-learn==1.7.1 \
    && conda clean --all --yes

ENV PATH=/opt/m5-native/bin:$PATH
ENV PYTHONDONTWRITEBYTECODE=1
WORKDIR /state

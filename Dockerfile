
FROM rust as volta-build
WORKDIR /src
RUN git clone https://github.com/volta-cli/volta.git /src
RUN git checkout tags/v2.0.2
RUN cargo build
RUN ls /src/target/debug

FROM python:3.12

# Set environment variables
ENV PIP_DISABLE_PIP_VERSION_CHECK 1
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set working directory
WORKDIR /app

# Copy project
COPY . /app/

# Install dependencies with Poetry
RUN pip3 install poetry

RUN poetry config virtualenvs.create false
RUN poetry install --no-root
# Copy over Volta binaries
RUN mkdir -p /root/.volta/bin
COPY --from=volta-build /src/target/debug/volta /root/.volta/bin
COPY --from=volta-build /src/target/debug/volta-migrate /root/.volta/bin
COPY --from=volta-build /src/target/debug/volta-shim /root/.volta/bin

# shell stuff for volta
SHELL ["/bin/bash", "-c"]
ENV BASH_ENV ~/.bashrc
ENV VOLTA_HOME /root/.volta
ENV PATH $VOLTA_HOME/bin:$PATH
RUN ln -s /root/.volta/bin/volta-shim /root/.volta/bin/node 
RUN ln -s /root/.volta/bin/volta-shim /root/.volta/bin/npm 
RUN ln -s /root/.volta/bin/volta-shim /root/.volta/bin/npx
RUN ln -s /root/.volta/bin/volta-shim /root/.volta/bin/pnpm 
RUN ln -s /root/.volta/bin/volta-shim /root/.volta/bin/yarn

# node installation
RUN volta install node
#RUN node -v && npm -v
RUN npm install

# generate front end assets
RUN poetry run python manage.py tailwind install
RUN poetry run python manage.py tailwind build
RUN poetry run python manage.py collectstatic --no-input

CMD poetry run python manage.py runserver 0.0.0.0:8000
# clean up
RUN rm -rf /app/node_modules

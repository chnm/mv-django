FROM rust as volta-build
WORKDIR /src
RUN git clone https://github.com/volta-cli/volta.git /src
RUN cargo build
RUN ls /src/target/debug

FROM python:slim-trixie
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set environment variables
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV UV_PROJECT_ENVIRONMENT=/venv

# Set working directory
WORKDIR /app

# Copy project
COPY . /app/

RUN uv lock

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
RUN npm install

# generate front end assets
RUN uv run manage.py tailwind install
RUN uv run manage.py tailwind build
RUN uv run manage.py collectstatic --no-input

# clean up
RUN rm -rf /root/.volta
RUN rm -rf /app/node_modules

CMD uv run manage.py runserver 0.0.0.0:8000

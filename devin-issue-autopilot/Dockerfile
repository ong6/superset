# Licensed to the Apache Software Foundation (ASF) under one or more
# contributor license agreements.  See the NOTICE file distributed with
# this work for additional information regarding copyright ownership.
# The ASF licenses this file to You under the Apache License, Version 2.0
# (the "License"); you may not use this file except in compliance with
# the License.  You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

FROM python:3.12-slim

ARG UID=1000
ARG GID=1000
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN groupadd --gid "$GID" autopilot \
    && useradd --create-home --uid "$UID" --gid "$GID" autopilot \
    && mkdir -p /data /app/reports \
    && chown -R autopilot:autopilot /data /app
WORKDIR /app
COPY --chown=autopilot:autopilot pyproject.toml README.md ./
COPY --chown=autopilot:autopilot autopilot ./autopilot
COPY --chown=autopilot:autopilot fixtures ./fixtures
COPY --chown=autopilot:autopilot tests ./tests
RUN pip install --no-cache-dir ".[dev]"

USER autopilot
CMD ["python", "-m", "autopilot", "watch"]

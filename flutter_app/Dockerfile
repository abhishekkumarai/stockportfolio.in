# Flutter web build, served by nginx.
FROM ghcr.io/cirruslabs/flutter:stable AS build
WORKDIR /app

COPY pubspec.yaml pubspec.lock ./
RUN flutter pub get

COPY . .

# API_URL is compiled into the bundle (a --dart-define), so it has to be a
# build arg; release builds fail loudly if it is missing (see lib/core/config.dart).
ARG API_URL=http://localhost:8001
RUN flutter build web --release --dart-define=API_URL=${API_URL}

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/build/web /usr/share/nginx/html
EXPOSE 80

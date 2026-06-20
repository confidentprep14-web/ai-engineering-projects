# Build guide: Dockerize Your App

## What you're building and why it matters

Docker is the unit of deployment for most cloud platforms. AWS Lambda, ECS, Cloud Run,
and Kubernetes all accept container images. If you can build a container that runs
your application, you can deploy it anywhere. The two concepts that trip people up:
multi-stage builds (keeping the final image small by not including build tools) and
volumes (keeping data outside the container so it survives restarts). Both are in
this project.

## The decision that matters in this build

**Multi-stage Dockerfile.** A single-stage build installs pip, gcc, and all build
tools in the final image. A multi-stage build installs them in a temporary builder
stage and copies only the compiled packages to the final image. The result: the image
that runs in production doesn't include anything that isn't needed at runtime.
This matters for security (smaller attack surface) and for pull time on cold starts.

## What will break

**`DATABASE_PATH` must point inside the named volume.** If it points to `/app/`
(the application directory), data is stored inside the container layer and lost on
restart. The Dockerfile creates `/data/` and the compose file mounts the named volume
there. Check that `.env` has `DATABASE_PATH=/data/chat_requests.db` — the old default
was `./chat_requests.db`, which would silently use the container layer.

**HEALTHCHECK timing.** Docker marks a container unhealthy after `retries` consecutive
failures. With `start_period=10s`, Docker ignores failures in the first 10 seconds.
If your app takes 15 seconds to start (dependency downloads, model loads), the container
will be marked unhealthy even if it is fine. Adjust `start_period` to match your startup time.

## How to talk about this in an interview

"I containerised a FastAPI application with a multi-stage Dockerfile — the final image
is under 500MB because build tools don't ship to production. I added a SQLite named
volume so data survives container restarts, and a health check so orchestrators know
when the container is actually ready. This is the same image format that goes into
AWS Lambda in the next step."

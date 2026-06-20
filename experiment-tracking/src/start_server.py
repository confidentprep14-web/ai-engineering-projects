"""Launch the local MLflow tracking server on port 5000."""
import subprocess


def main():
    print("Starting MLflow server at http://localhost:5000")
    try:
        subprocess.run(
            [
                "mlflow",
                "server",
                "--host",
                "0.0.0.0",
                "--port",
                "5000",
                "--backend-store-uri",
                "./mlruns",
                "--default-artifact-root",
                "./mlruns",
            ]
        )
    except PermissionError as e:
        print(f"Permission error starting server: {e}")
        print("Suggestion: chmod 755 mlruns/")
        raise


if __name__ == "__main__":
    main()

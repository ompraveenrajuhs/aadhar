# Aadhar-CICD

Java 21 + Maven project with CI coverage enforcement and AI-assisted test generation.

## What is included

- Maven project scaffold with sample code in `src/main/java`
- JUnit 5 tests in `src/test/java`
- JaCoCo coverage check at **80% minimum line coverage**
- GitHub workflow `test-gen.yml` that generates tests using Ollama on a self-hosted runner
- GitHub workflow `ci.yml` that runs `mvn verify` and uploads JaCoCo report
- Path filters in `test-gen.yml` to skip docs-only and unrelated changes

## Project structure

- `pom.xml`: dependencies, test plugins, JaCoCo threshold
- `.github/workflows/test-gen.yml`: AI test generation and PR creation to `auto-tests`
- `.github/workflows/ci.yml`: test + coverage validation on `auto-tests` and `main`
- `scripts/find_test_targets.py`: changed files + transitive dependent target selection
- `scripts/generate_tests_with_ollama.py`: prompts Ollama and writes generated test files

## Local quick start

```powershell
mvn test
mvn verify
```

## Optional local run

```powershell
mvn -q -DskipTests package
java -cp target\aadhar-cicd-1.0.0-SNAPSHOT.jar com.aadhar.App 123412341230
```

## GitHub setup checklist

1. Create and protect `auto-tests` branch.
2. Configure branch protection requiring:
   - `CI / verify` status check
   - Any 1 approval
3. Ensure self-hosted runner is online and has:
   - Java 21
   - Maven
   - Python 3.11+
   - Ollama installed and model pulled (default `llama3.1`)
4. Add repository label(s) if desired (for example `automated-tests`, `needs-review`).

## Notes

- The Ollama workflow assumes `auto-tests` already exists in remote.
- Generated tests can fail if model output is invalid Java; the workflow catches this by running Maven tests.
- Test generation runs only when configured source/build/workflow paths change, and can still be triggered manually via workflow dispatch.

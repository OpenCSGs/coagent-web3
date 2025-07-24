# Example

## Usage

### Build

Create a specification file `specification.json`:

```bash
cd example
cp specification.sample.json specification.json
```

Edit the `specification.json` file to your liking.

Build an agent:

```bash
web3-build --spec=./specification.json --out=./out
```

### Run

Edit the generated `.env` file to your liking.

Run the generated agent:

```bash
cd out
uv run .
```

Send a message in Telegram to your agent.

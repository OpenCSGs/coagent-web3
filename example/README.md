# Example

## Usage

### Build

Create a character file `character.json`:

```bash
cd example
cp character.sample.json character.json
```

Edit the `character.json` file to your liking.

Build an agent:

```bash
web3-build --character=./character.json --out=./out
```

### Run

Edit the generated `.env` file to your liking.

Run the generated agent:

```bash
cd out
uv run .
```

Send a message in Telegram to your agent.

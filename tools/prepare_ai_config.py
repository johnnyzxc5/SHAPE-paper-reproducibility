"""Create a separate path-adapted resolved config; never run a scientific job."""
from pathlib import Path
import argparse
import json

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--record', type=Path, required=True)
    parser.add_argument('--index', type=Path, required=True)
    parser.add_argument('--output-root', type=Path, required=True)
    parser.add_argument('--destination', type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    destination = args.destination.resolve()
    output = args.output_root.resolve()
    # New writable material belongs in local/; frozen metadata cannot be overwritten.
    for path in [destination, output]:
        if not path.is_relative_to(root / 'local'):
            parser.error('New config and output paths must be below this repository/local/')
    if not args.index.is_file():
        parser.error('The index must already exist; it will not be generated or modified.')
    config = json.loads(args.record.read_text(encoding='utf-8'))
    config['index_path'] = str(args.index.resolve())
    config['output_root'] = str(output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open('x', encoding='utf-8') as stream:
        json.dump(config, stream, indent=2)
        stream.write('\n')
    print(destination)

if __name__ == '__main__':
    main()

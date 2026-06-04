import asyncio
import argparse
import logging
from agent import Autoagent

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def parse_args():
    parser = argparse.ArgumentParser(description='Product Details Extractor')
    parser.add_argument('-o', '--output', help='Output CSV file', required=True)
    return parser.parse_args()

async def main():
    try:
        args = parse_args()
        agent = Autoagent()
        await agent.extract_and_save(args.output)
    except KeyboardInterrupt:
        logging.info('Shutdown requested')
    except Exception as e:
        logging.error(f'Error: {e}')
    finally:
        logging.info('Exiting')

if __name__ == '__main__':
    asyncio.run(main())

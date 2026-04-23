import asyncio
import argparse
import logging
from agent import PdfSummarizer

logging.basicConfig(level=logging.INFO)

def parse_args():
    parser = argparse.ArgumentParser(description='PDF Summarizer')
    parser.add_argument('--input', help='Input PDF file')
    parser.add_argument('--output', help='Output summary file')
    return parser.parse_args()

async def main():
    try:
        args = parse_args()
        agent = PdfSummarizer()
        await agent.summarize(args.input, args.output)
    except KeyboardInterrupt:
        logging.info('Shutdown requested')
    except Exception as e:
        logging.error(f'Error: {e}')

if __name__ == '__main__':
    asyncio.run(main())

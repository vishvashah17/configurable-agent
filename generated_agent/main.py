import asyncio
import argparse
import logging
from agent import Customerinsightsagent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def parse_args():
    parser = argparse.ArgumentParser(description='Customer Insights Agent')
    return parser.parse_args()

async def main():
    try:
        agent = Customerinsightsagent()
        await agent.run()
    except KeyboardInterrupt:
        logger.info('Shutdown requested')
    except Exception as e:
        logger.error(f'Error: {e}')

if __name__ == '__main__':
    args = parse_args()
    asyncio.run(main())

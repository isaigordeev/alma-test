import asyncio
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("flag-demo")


async def send_message_on_flag(flag: asyncio.Event):
    while True:
        await flag.wait()  # wait until flag is set
        logger.info("Flag was set! Sending message...")
        # simulate sending message
        await asyncio.sleep(0.1)
        logger.info("Message sent.")
        flag.clear()  # reset flag to wait for next trigger


async def trigger_flag_periodically(flag: asyncio.Event):
    for i in range(3):
        await asyncio.sleep(2)
        logger.info(f"Triggering flag #{i + 1}")
        flag.set()
    logger.info("Done triggering flag — stopping demo.")
    await asyncio.sleep(2)
    # this script never exits because the loop above is infinite,
    # so we'll cancel all tasks after the demo.
    for task in asyncio.all_tasks():
        task.cancel()


async def main():
    flag = asyncio.Event()

    sender_task = asyncio.create_task(send_message_on_flag(flag))
    trigger_task = asyncio.create_task(trigger_flag_periodically(flag))

    try:
        await asyncio.gather(sender_task, trigger_task)
    except asyncio.CancelledError:
        logger.info("Tasks cancelled, exiting cleanly.")


if __name__ == "__main__":
    asyncio.run(main())

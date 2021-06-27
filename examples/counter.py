import areo

loop = areo.get_loop()

async def counter():
    for i in range(10):
        print(i)
        await areo.sleep(1)

async def main():

    tasks = []
    for _ in range(5):
        tasks.append(counter())

    await areo.wait(tasks)

loop.run_until_done(main())
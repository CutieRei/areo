import areo

loop = areo.get_loop()

def work():
    fut = loop.create_future()
    loop.call_later(5, fut.set_result, "im home!")
    return fut

async def main():

    try:
        await areo.wait_for(work(), 2)
    except Exception as exc:
        print("ive been waiting for too long!")

loop.run_until_done(main())
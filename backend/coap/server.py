import datetime
import logging

import asyncio

import aiocoap.resource as resource
import aiocoap


MSG_TYPE={
    'short': b"It is a simple short response.\n",
    'middle': b"Lorem ipsum dolor sit amet, consectetur adipiscing elit. Integer nisl magna, varius et nunc ut, pharetra posuere ante. "\
            b"Praesent vestibulum tempor vehicula. Nunc vehicula a elit at rhoncus. Proin luctus ex at sapien pretium, a consequat magna maximus. "\
            b"Nunc scelerisque nunc et enim pellentesque, eu porta diam aliquet. Mauris mollis congue justo, ac volutpat nibh consequat sit amet. "\
            b"Vestibulum ante ipsum primis in faucibus orci luctus et ultrices posuere cubilia curae; Curabitur congue nibh ut efficitur est.\n\n",
    'long': b"Lorem ipsum dolor sit amet, consectetur adipiscing elit. Integer quam nulla, tincidunt nec dolor ut, "\
            b"convallis finibus est. Aenean pretium nulla eu dolor ultrices maximus. Phasellus laoreet metus et pellentesque ornare. "\
            b"Praesent ac purus sed quam pulvinar cursus. Suspendisse dictum mollis est non tincidunt. In posuere mauris justo, "\
            b"nec rhoncus tortor vestibulum at. Aenean in lorem augue. Maecenas ante elit, tempor id ante in, pellentesque congue nisl.\n\n"\
            b"Curabitur sit amet pulvinar turpis. Suspendisse potenti. Aenean porta, arcu sed sollicitudin commodo, ante dolor suscipit eros, "\
            b"vitae eleifend velit felis ac risus. Sed vehicula mi sed ultrices ullamcorper. Nulla fringilla ac lacus viverra egestas. "\
            b"Suspendisse metus ligula, ultricies et egestas in, sodales vitae nunc. Quisque aliquam dolor fringilla venenatis aliquam. "\
            b"Praesent tellus diam, luctus eu risus in, scelerisque auctor nunc. Donec odio nibh, venenatis eget condimentum eu, tristique "\
            b"facilisis nunc. Proin arcu ex, congue malesuada consequat a, tempor eu justo. Vivamus sapien magna, venenatis at interdum ut, "\
            b"eleifend eget velit.\n\n"\
            b"Sed a efficitur eros. Vestibulum mattis blandit malesuada. Donec leo quam, facilisis ac tortor eu, fringilla tempus neque. "\
            b"Vestibulum volutpat, diam vel vulputate molestie, nunc velit mollis ipsum, vitae pulvinar urna neque nec leo. Curabitur elit tortor, "\
            b"venenatis sed malesuada at, efficitur quis risus. Fusce ac tellus et ipsum viverra consequat. Proin pretium commodo lacus, "\
            b"quis vestibulum nisl consequat eu. Morbi maximus, neque in tempus finibus, lacus odio tempus magna, sit amet pretium libero.\n\n"
}


class CoAPResource(resource.Resource):
    def __init__(self, url):
        super().__init__()
        self.url = url
        self.content = MSG_TYPE[url]

    async def render_get(self, request):
        if request.mtype == aiocoap.NON:
            return aiocoap.Message(payload=self.content, mtype=aiocoap.NON)
        return aiocoap.Message(payload=self.content)

    async def render_post(self, request):
        if request.payload == self.content:
            logging.getLogger("coap-server").info(f'[coap://{self.url}|POST][Succesfully received correct payload!]')
            return aiocoap.Message(mtype=request.mtype, code=aiocoap.CREATED)

        return aiocoap.Message(mtype=request.mtype, code=aiocoap.BAD_REQUEST) 


logging.basicConfig(level=logging.INFO)
logging.getLogger("coap-server").setLevel(logging.DEBUG)

def main():
    # Resource tree creation
    root = resource.Site()

    root.add_resource(['.well-known', 'core'],
            resource.WKCResource(root.get_resources_as_linkheader))
    root.add_resource(['short'], CoAPResource('short'))
    root.add_resource(['middle'], CoAPResource('middle'))
    root.add_resource(['long'], CoAPResource('long'))

    asyncio.Task(aiocoap.Context.create_server_context(root, bind=('::', 31416)))

    asyncio.get_event_loop().run_forever()

if __name__ == "__main__":
    main()
import asyncio
import ssl

import backoff
import websockets


class RetryableError(Exception):
    pass


class Core(object):
    def __init__(self, args, camera, logger):
        self.host = args.host
        self.token = args.token
        self.mac = args.mac
        self.logger = logger
        self.cam = camera

        # Set up ssl context for requests
        self.ssl_context = ssl.create_default_context()
        self.ssl_context.check_hostname = False
        self.ssl_context.verify_mode = ssl.CERT_NONE
        self.ssl_context.load_cert_chain(args.cert, args.cert)

    async def run(self) -> None:
        uri = "wss://{}:7442/camera/1.0/ws?token={}".format(self.host, self.token)
        headers = {"camera-mac": self.mac}
        has_connected = False

        @backoff.on_predicate(
            backoff.expo,
            lambda retryable: retryable,
            factor=2,
            jitter=None,
            max_value=10,
            logger=self.logger,
        )
        async def connect():
            nonlocal has_connected
            self.logger.info(f"Creating ws connection to {uri}")
            try:
                ws = await websockets.connect(
                    uri,
                    extra_headers=headers,
                    ssl=self.ssl_context,
                    subprotocols=["secure_transfer"],
                )
                has_connected = True
            except websockets.exceptions.InvalidStatusCode as e:
                # Hitting rate-limiting
                if e.status_code == 429:
                    return True
                raise
            except ConnectionRefusedError:
                if has_connected:
                    return True
                raise

            try:
                await asyncio.gather(self.cam._run(ws), self.cam.run())
            except RetryableError:
                return True
            finally:
                await self.cam.close()

        await connect()

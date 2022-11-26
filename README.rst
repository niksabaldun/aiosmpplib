aiosmpplib
==========
An asynchronous SMPP library for use with asyncio.

Inspired by `naz`_ library by Komu Wairagu. Initial intention was to add missing functionality
to existing library. But in the end, the code has been almost completely rewritten and released
as a separate library.

    SMPP is a protocol designed for the transfer of short message data between External Short
    Messaging Entities(ESMEs), Routing Entities(REs) and Short Message Service Center(SMSC).
    - `Wikipedia <https://en.wikipedia.org/wiki/Short_Message_Peer-to-Peer>`_

Currently, only partial ESME functionality is implemented, and only SMPP version 3.4 is supported.

Full documentation is not available at this time.

.. _naz: https://github.com/komuw/naz

Installation
------------
.. code-block:: shell

    pip install aiosmpplib


Requirements
------------
Python 3.7+ is required. Currently, aiosmpplib does not have any third-party dependencies,
but it optionally uses `orjson`_ library for JSON serialization and logging.

.. _orjson: https://github.com/ijl/orjson


Quick start
-----------

.. code-block:: python

    import asyncio
    from aiosmpplib import ESME, PhoneNumber, SubmitSm
    from aiosmpplib.log import DEBUG

    async def main():
        # Create ESME instance.
        esme = ESME(
            smsc_host='127.0.0.1',
            smsc_port=2775,
            system_id='test',
            password='test',
            log_level=DEBUG,
        )

        # Queue messages to send.
        for i in range(0, 5):
            msg = SubmitSm(
                short_message=f'Test message {i}',
                source=PhoneNumber('254722111111'),
                destination=PhoneNumber('254722999999'),
                log_id=f'id-{i}',
            )
            await esme.broker.enqueue(msg)

        # Start ESME. It will run until stopped, automatically reconnecting if necessary.
        # If you want to test connection beforehand, await esme.connect() first.
        # It will raise an exception if connection is not successfull -
        # typically SmppError, or one of transport errors (OSError, TimeoutError, socket.error etc).
        asyncio.create_task(esme.start())
        # Give it some time to send messages.
        await asyncio.sleep(20)
        # Stop ESME.
        await esme.stop()

    if __name__ == "__main__":
        loop = asyncio.get_event_loop()
        loop.run_until_complete(main())
        loop.close()


Quick user guide
----------------
Your application interacts with ESME via three interfaces: broker, correlator and hook.

* Broker is a FIFO queue in which your application puts messages. ESME retrieves messages
  from the broker and sends them to SMSC. Any type of SMPP message can be queued, but it really
  only makes sense for **SubmitSm** (outgoing SMS). Subclass **AbstractBroker** in order to put and
  get messages from persistent storage. The library provides ``json_encode`` and ``json_decode``
  convenience methods which can be used to convert messages to/from JSON. Again, while any message
  can be serialized, it probably only makes sense for **SubmitSm**, and possibly **DeliverSm**.
* Correlator is an interface that does two types of correlation:

  * Outgoing SMPP requests are correlated with received responses.
  * Outgoing SMS messages (SubmitSm) are correlated with delivery receipts (DeliverSm).

  Delivery receipts may be received days after original message is sent, so this type of
  correlation should be persisted. Subclass **SimpleCorrelator** and override ``put_delivery`` and
  ``get_delivery`` methods. If you want to implement more efficient request/response correlation,
  subclass **AbstractCorrelator** and also override ``get`` and ``put`` methods.
* Hook is an interface with three async methods:

  * ``sending``: Called before sending any message to SMSC.
  * ``received``: Called after receiving any message from SMSC.
  * ``send_error``: Called if error occured while sending a SubmitSm.

  Subclass **AbstractHook** and implement all three methods. The latter two are essential for
  reliable message tracking.

Incoming message flow
_____________________
Receiving messages is straightforward. The ``received`` hook will be called. If the
``smpp_message`` parameter is of type **DeliverSm** and its ``is_receipt`` method returns ``False``,
it is an incoming SMS. Store it as appropriate.

Outgoing message flow
_____________________
Sending messages is a lot more involved.

1. Create a **SubmitSm** message with unique ``log_id`` and optionally ``extra_data`` parameters.
   Any message related to this message will have the same ``log_id`` and ``extra_data``,
   provided that correlator did its job.
2. Enqueue the message in broker.
3. If message could not be sent, ``send_error`` hook will be called. Original message is available
   in ``smpp_message`` parameter. The ``error`` parameter contains exception that occured.

   * ValueError indicates that the message couldn't be encoded to PDU (probably invalid parameters).
   * Transport errors (OSError and its descendants) indicate a network problem.
   * TimeoutError indicates that the response from SMSC was not received within timeout.
     Timeout duration depends on correlator implementation.

   Whichever error occured, the message will not be re-sent automatically.
   User application must implement retry mechanism, if required.
4. If the SMSC does respond, check the response in ``received`` hook.
   The ``smpp_message`` parameter will be either:

   * **SubmitSmResp** - If ``command_status`` member is anything other than
     ``SmppCommandStatus.ESME_ROK``, the request has been rejected by SMSC.
   * **GenericNack** - The request was not understood by SMSC, probably due to network error.

   Again, if the message was rejected, it will not be re-sent automatically.
5. If the request was accepted, a delivery receipt should arrive after some time.
   In ``received`` hook, look for **DeliverSm** message whose ``is_receipt`` method
   returns ``True``. Then use ``parse_receipt`` method to get a dictionary with parsed data.
   Receipt structure is SMSC-specific, but it usually has the following items:
   
   .. code-block:: python

       {
           'id': str # Message ID allocated by the SMSC when submitted.
           'sub': int # Number of short messages originally submitted.
           'dlvrd': int # Number of short messages delivered.
           'submit date': datetime # The time and date at which the message was submitted.
           'done date': datetime # The time and date at which the message reached its final state.
           'stat': str # The final status of the message.
           'err': str # Network specific error code or an SMSC error code.
           'text': str # The first 20 characters of the short message.
       }
   
   The ``stat`` parameter should have one the following values:

   * ``DELIVRD`` - Message is delivered to destination.
   * ``EXPIRED`` - Message validity period has expired.
   * ``DELETED`` - Message has been deleted.
   * ``UNDELIV`` - Message is undeliverable.
   * ``ACCEPTD`` - Message is in accepted state.
   * ``UNKNOWN`` - Message is in invalid state.
   * ``REJECTD`` - Message is in a rejected state.

   For more details, check `SMPP specification <https://smpp.org/SMPP_v3_4_Issue1_2.pdf>`_.

Example hook implementation:
____________________________

.. code-block:: python

    from aiosmpplib import AbstractHook, SmppCommandStatus
    from aiosmpplib import DeliverSm, SubmitSm, SubmitSmResp, GenericNack, SmppMessage, Trackable

    class MyHook(AbstractHook):
        async def _save_result(self, msg: str, smpp_message: Trackable) -> None:
            log_id: str = smpp_message.log_id
            extra_data: str = smpp_message.extra_data
            # Save data to database

        async def sending(self, smpp_message: SmppMessage, pdu: bytes, client_id: str) -> None:
            pass # Or trace log

        async def received(self, smpp_message: Optional[SmppMessage], pdu: bytes,
                           client_id: str) -> None:
            if isinstance(smpp_message, GenericNack):
                await self._save_result('Sending failed', smpp_message)
                # Requeue if desired
            if isinstance(smpp_message, SubmitSmResp):
                if smpp_message.command_status == SmppCommandStatus.ESME_ROK:
                    await self._save_result('Message sent', smpp_message)
                else:
                    await self._save_result('Sending failed', smpp_message)
                    # Requeue if desired
            elif isinstance(smpp_message, DeliverSm):
                if smpp_message.is_receipt():
                    # This is a delivery receipt
                    receipt: Dict[str, Any] = smpp_message.parse_receipt()
                    final_status: str = receipt.get('stat', '')
                    if final_status == 'DELIVRD':
                        msg: str = 'Delivered to handset'
                    elif final_status == 'EXPIRED':
                        msg: str = 'Message expired'
                    elif final_status == 'DELETED':
                        msg: str = 'Message deleted by SC'
                    elif final_status == 'UNDELIV':
                        msg: str = 'Message undeliverable'
                    elif final_status == 'ACCEPTD':
                        msg: str = 'Message accepted'
                    elif final_status == 'REJECTD':
                        msg: str = 'Message rejected'
                    else:
                        msg: str = 'Unknown status'
                    await self._save_result(msg, smpp_message)
                else:
                    pass
                    # This is an incoming SMS
                    # Process and save to database

        async def send_error(self, smpp_message: SmppMessage, error: Exception, client_id: str) -> None:
            if isinstance(smpp_message, SubmitSm):
                await self._save_result('Sending failed', smpp_message)
                # Requeue if desired


Bug Reporting
-------------
Bug reports and feature requests are welcome via `Github issues`_.

.. _Github issues: https://github.com/niksabaldun/aiosmpplib/issues

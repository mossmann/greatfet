#!/usr/bin/env python3
#
# This file is part of GreatFET

from __future__ import print_function

import os
import sys
import usb1
import time
import errno
import timeit


import greatfet
from greatfet import GreatFET
from greatfet.utils import log_silent, log_verbose, GreatFETArgumentParser, from_eng_notation, eng_notation


DEFAULT_TRANSFER_SIZE    = 0x4000
DEFAULT_BENCHMARK_LENGTH = 128 * 1024 * 1024 # 16 MiB
ASYNC_TRANSFER_COUNT     = 4


def run_sync_benchmark(gf, data_to_transfer):
    """ Runs a benchmark of synchronous USB communications. """

    total_data = 0

    # Reserve the interface we're going to use for communication.
    gf.comms.device.claimInterface(1)

    print("Starting a benchmark of synchronous USB communications: transferring {} MiB.".format(data_to_transfer / 1024 / 1024))

    # Ask the GreatFET to start performing USB transfers.
    gf.apis.benchmarking.start_upload()

    # Repeatedly perform transfers, and measure our timing.
    try:
        start_time = timeit.default_timer()
        while total_data < data_to_transfer:
            result = gf.comms.device.bulkRead(1, DEFAULT_TRANSFER_SIZE, 3000)
            total_data += len(result)
    except KeyboardInterrupt:
        pass

    end_time = timeit.default_timer()
    total_seconds = end_time - start_time


    # Release our claim on the relevant interface, and stop our benchmarking.
    gf.apis.benchmarking.stop()
    gf.comms.device.releaseInterface(1)

    # Finally, print our test results.
    data_mib  = round(total_data / 1024 / 1024, 2)
    speed_mib = round(data_mib / total_seconds, 2)

    print("Transferred {} MiB in {} seconds. (Speed: {} MiB/s)".format(data_mib, total_seconds, speed_mib))


def run_async_benchmark(gf, data_to_transfer):
    """ Runs a benchmark of an async USB communications. """

    benchmark_active = True
    total_data = 0
    transfers  = []

    def transfer_complete(transfer):
        """ Callback function called when a transfer is complete. """

        nonlocal total_data

        if not benchmark_active:
            return

        status = transfer.getStatus()
        if status == usb1.TRANSFER_COMPLETED:
            total_data += transfer.getActualLength()

        # Re-submit the transfer, so it can be processed again.
        try:
            transfer.submit()

        # If the transfer was "doomed", that means our main program requested it
        # not be resubmitted. We'll silently accept this, as it means we're shutting down.
        except usb1.DoomedTransferError:
            pass

        # Our firmware shouldn't ever generate stalls; but some OS's (*cough* macOS *cough*)
        # generate stalls intermittently when their own data pipeline is full. We'll clear the
        # condition and try re-submitting anyway.
        except usb1.USBErrorPipe:
            gf.comms.device.clearHalt(1)
            transfer.submit()


    # Reserve the interface we're going to use for communication.
    gf.comms.device.claimInterface(1)
    print("Starting a benchmark of asynchronous USB communications: transferring {} MiB.".format(data_to_transfer / 1024 / 1024))

    # Ask the GreatFET to start performing USB transfers. This won't skew our benchmark; as things are locked
    # on the PC being able to communicate.
    gf.apis.benchmarking.start_upload()

    # Pre-schedule a collection of asynchronous USB transfers.
    for _ in range(ASYNC_TRANSFER_COUNT):

        # Populate the transfer object...
        transfer = gf.comms.device.getTransfer()
        transfer.setBulk(usb1.ENDPOINT_IN | 1, DEFAULT_TRANSFER_SIZE, callback=transfer_complete, timeout=3000)

        # ... and submit it for processing.
        transfer.submit()
        transfers.append(transfer)

    # Repeatedly perform transfers, and measure our timing.
    start_time = timeit.default_timer()
    while total_data < data_to_transfer:
        try:
            gf.comms.handle_events()
        except usb1.USBErrorInterrupted:
            pass

    end_time = timeit.default_timer()
    total_seconds = end_time - start_time
    benchmark_active = False

    # Release our claim on the relevant interface, and stop our benchmarking.
    gf.apis.benchmarking.stop()

    for transfer in transfers:
        transfer.doom()

    gf.comms.device.releaseInterface(1)

    # Finally, print our test results.
    data_mib  = round(total_data / 1024 / 1024, 2)
    speed_mib = round(data_mib / total_seconds, 2)

    print("Transferred {} MiB in {} seconds. (Speed: {} MiB/s)".format(data_mib, total_seconds, speed_mib))


def main():

    # Simple type-arguments for parsing.
    size_from_string = lambda x : from_eng_notation(x, units=['iB', 'B'], to_type=int)

    # Set up a simple argument parser.
    parser = GreatFETArgumentParser(description="Benchmark GreatFET usb performance.")
    parser.add_argument('--sync-usb', dest="sync", action="store_true", help="Test synchronous bulk performance.")
    parser.add_argument('--async-usb', dest="asynch", action="store_true", help="Test asynchronous bulk performance.")
    parser.add_argument('--data-to-transfer', metavar='bytes', type=size_from_string, default=DEFAULT_BENCHMARK_LENGTH,
                         dest='length', help='total data to transfer (default: 16 MiB)')
    args = parser.parse_args()

    args = parser.parse_args()
    gf = parser.find_specified_device()

    if args.sync:
        run_sync_benchmark(gf, args.length)
    elif args.asynch:
        run_async_benchmark(gf, args.length)
    else:
        print(parser.print_help())

    os._exit(0)


if __name__ == '__main__':
    main()

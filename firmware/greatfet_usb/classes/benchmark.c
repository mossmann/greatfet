/*
 * This file is part of GreatFET
 */

#include <drivers/comms.h>
#include <debug.h>

#include <drivers/usb/usb.h>
#include <drivers/usb/usb_queue.h>

#include "../usb_bulk_buffer.h"
#include "../usb_endpoint.h"
#include "../usb_streaming.h"

#include <stddef.h>
#include <errno.h>
#include <ctype.h>

#define CLASS_NUMBER_SELF (0x117)


bool usb_benchmark_enabled = false;


static int _verb_start_upload_benchmark(struct command_transaction *trans)
{
	(void)trans;

	usb_benchmark_enabled = true;
	usb_endpoint_init(&usb0_endpoint_bulk_in);

	return 0;
}


static int _verb_stop_upload_benchmark(struct command_transaction *trans)
{
	(void)trans;

	usb_benchmark_enabled = false;
	usb_endpoint_disable(&usb0_endpoint_bulk_in);

	return 0;
}


void service_benchmarking(void)
{
	static unsigned transfers = 0;

	// If we're performing USB benchmarking, send garbage data up to the host.
	if (usb_benchmark_enabled) {
		usb_transfer_schedule_wait(
			&usb0_endpoint_bulk_in,
			&usb_bulk_buffer,
			USB_STREAMING_BUFFER_SIZE, 0, 0, 0);

		++transfers;
		if ((transfers % 10000) == 0) {
			led_toggle(LED4);
		}
	}
}



/**
 * Verbs for the firmware API.
 */
static struct comms_verb _verbs[] = {

		// USB benchmarking.
		{  .name = "start_upload", .handler = _verb_start_upload_benchmark, .in_signature = "", .out_signature = "",
           .doc = "Starts a benchmark of USB comms upload performance" },
		{  .name = "stop", .handler = _verb_stop_upload_benchmark, .in_signature = "", .out_signature = "",
           .doc = "Stops the running benchmark." },

		{}
};
COMMS_DEFINE_SIMPLE_CLASS(benchmarking, CLASS_NUMBER_SELF, "benchmarking", _verbs,
        "Class for performance measurement of GreatFET communications.")


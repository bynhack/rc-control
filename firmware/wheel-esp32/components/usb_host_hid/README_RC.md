Copy of espressif/usb_host_hid 1.2.1 (Apache-2.0, see LICENSE) with one
addition for rc-control: hid_host_device_send_output_report(), which sends an
output report on the interface's interrupt OUT endpoint. The MOZA R5 ignores
force feedback reports sent with SET_REPORT on the control pipe.

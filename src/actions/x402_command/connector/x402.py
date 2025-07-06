import base64
import json
import logging
import os
from datetime import datetime

import requests
from eth_account import Account

from actions.base import ActionConfig, ActionConnector
from actions.move_safe.interface import MoveInput

# EIP712 domain data
domain_type_data = [
    {"name": "name", "type": "string"},
    {"name": "version", "type": "string"},
    {"name": "chainId", "type": "uint256"},
    {"name": "verifyingContract", "type": "address"},
]

# EIP712 message data
transfer_type_data = {
    "TransferWithAuthorization": [
        {"name": "from", "type": "address"},
        {"name": "to", "type": "address"},
        {"name": "value", "type": "uint256"},
        {"name": "validAfter", "type": "uint256"},
        {"name": "validBefore", "type": "uint256"},
        {"name": "nonce", "type": "bytes32"},
    ]
}


class X402Connector(ActionConnector[MoveInput]):
    def __init__(self, config: ActionConfig):
        super().__init__(config)

        self.private_key = getattr(self.config, "private_key", None)
        self.x402_endpoint = getattr(self.config, "x402_endpoint", None)

        self.network = getattr(self.config, "network", None)
        self.max_amount_required = getattr(self.config, "max_amount_required", None)
        self.max_timeout_seconds = getattr(self.config, "max_timeout_seconds", None)
        self.pay_to = getattr(self.config, "pay_to", None)

    async def connect(self, output_interface: MoveInput) -> None:
        """
        Connect to the X402 endpoint and send the message.
        """
        if self.x402_endpoint is None:
            logging.error("X402 endpoint is not set.")
            return

        if self.private_key is None:
            logging.error("Private key is not set.")
            return

        if self.max_amount_required is None:
            response = requests.post(self.x402_endpoint)
            if response.status_code == 402:
                try:
                    payment_response = response.json()
                    payment_requirements = payment_response.get("accepts", None)
                    if payment_requirements is None or len(payment_requirements) == 0:
                        logging.error("Payment requirements not found.")
                        return
                    payment_requirement = payment_requirements[0]
                    self.max_amount_required = payment_requirement.get(
                        "maxAmountRequired", None
                    )
                    self.max_timeout_seconds = payment_requirement.get(
                        "maxTimeoutSeconds", None
                    )
                    self.pay_to = payment_requirement.get("payTo", None)
                    self.network = payment_requirement.get("network", None)
                except Exception as e:
                    logging.error(f"Failed to parse payment requirements: {e}")
                    return

        if None in (
            self.max_amount_required,
            self.max_timeout_seconds,
            self.pay_to,
            self.network,
        ):
            logging.error("Payment requirements are not set.")
            return

        account = Account.from_key(self.private_key)
        sender_address = account.address

        current_time = int(datetime.now().timestamp())
        valid_after = 0
        valid_before = current_time + int(self.max_timeout_seconds) * 2

        nonce = os.urandom(32)

        # Hardcode USDC address and chain ID based on the network
        usdc_address = (
            "0x036CbD53842c5426634e7929541eC2318f3dCF7e"
            if self.network == "base-sepolia"
            else "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
        )
        chain_id = 84532 if self.network == "base-sepolia" else 8453

        domain_data = {
            "name": "USDC",
            "version": "2",
            "chainId": chain_id,
            "verifyingContract": usdc_address,
        }

        message_data = {
            "from": sender_address,
            "to": self.pay_to,
            "value": str(self.max_amount_required),
            "validAfter": str(valid_after),
            "validBefore": str(valid_before),
            "nonce": "0x" + nonce.hex(),
        }

        signed_msg = Account.sign_typed_data(
            self.private_key, domain_data, transfer_type_data, message_data
        )

        payload = {
            "x402Version": 1,
            "scheme": "exact",
            "network": self.network,
            "payload": {
                "signature": "0x" + signed_msg.signature.hex(),
                "authorization": message_data,
            },
        }
        encoded_payload = base64.b64encode(json.dumps(payload).encode("utf-8")).decode(
            "utf-8"
        )

        logging.info(
            f"Sending payload to X402 endpoint: {self.x402_endpoint} with the action: {output_interface.action}"
        )

        headers = {
            "X-PAYMENT": encoded_payload,
            "content-type": "application/json",
        }
        try:
            response = requests.post(
                self.x402_endpoint,
                headers=headers,
                json={"message": output_interface.action},
            )
            if response.status_code == 200:
                logging.info(
                    f"x402 payment successful with the connected action: {output_interface.action}"
                )
            else:
                logging.error(
                    f"Payment failed with status code: {response.status_code}"
                )
                logging.error(f"Response: {response.text}")
        except Exception as e:
            logging.error(f"Error sending x402 request: {e}")
            return

from telegram import Update
from telegram.ext import (Application, CommandHandler, ContextTypes,
                          MessageHandler, filters)

from dotenv import load_dotenv

import asyncio
import os
import logging
import socket
import os

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

import bitcoin

load_dotenv()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text('Send me a Bitcoin transaction in raw format.')

async def handle_transaction(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tx_raw = update.message.text
    is_valid, message = validate_transaction(tx_raw)
    if is_valid:
        # Form the message to send to the server
        message_to_send = f"add_tx {tx_raw}"
        # Send the transaction to the server
        server_response = await send_to_server(message_to_send)
        if server_response:
            await update.message.reply_text('Transaction processed. Server response: ' + server_response)
        else:
            await update.message.reply_text('Failed to communicate with server.')
    else:
        await update.message.reply_text('Transaction validation failed: ' + message)

async def send_to_server(message):
    host = os.getenv('SERVER_IP')
    port = int(os.getenv('SERVER_PORT'))
    reader, writer = None, None
    try:
        reader, writer = await asyncio.open_connection(host, port)
        writer.write(message.encode())
        await writer.drain()
        response = await reader.read(100)
        print(f"Server response: {response.decode()}")
        return response.decode()
    except Exception as e:
        print(f"Failed to send to server: {e}")
        return None
    finally:
        if writer:
            writer.close()
            await writer.wait_closed()

def validate_transaction(tx_raw):
    try:
        logging.info("Deserializing transaction")
        logging.info(f"Received tx_raw: {tx_raw[:50]}")  # prints first 50 chars of tx_raw

        tx_raw = tx_raw.strip()  # Remove leading/trailing whitespace
        tx_raw = ''.join(tx_raw.split())  # Remove all whitespace

        # Validate that the transaction string is hexadecimal
        if any(c not in "0123456789abcdefABCDEF" for c in tx_raw):
            return False, "Transaction data contains non-hexadecimal characters."
        
        tx = bitcoin.deserialize(tx_raw)

        logging.info(f"Transaction inputs: {len(tx['ins'])}, outputs: {len(tx['outs'])}")
        # Check for equal number of inputs and outputs
        if len(tx['ins']) != len(tx['outs']):
            logging.error("Input-output mismatch")
            return False, "The number of inputs does not match the number of outputs."
        
        # Check for maximum 5 inputs
        if len(tx['ins']) > 5:
            logging.error("Too many inputs")
            return False, "The transaction has more than 5 inputs."
        
        # Check locktime
        logging.info(f"Transaction locktime: {tx['locktime']}")
        if tx['locktime'] != 0:
            logging.error("Incorrect locktime")
            return False, "The transaction's locktime must be 0."
        
        # Check each input for the correct SigHash type
        for index, input in enumerate(tx['ins']):
            if 'witness' in input and input['witness']:
                logging.info(f"Witness for input {index}: {input['witness']}")
                
                if len(input['witness']) != 2:
                    logging.error("Incorrect witness length")
                    return False, "Script is not a P2WPKH"
                
                # Assuming the SigHash type is the last byte of the last item in the witness
                last_byte = input['witness'][-1][-1]
                logging.info(f"SigHash type for input {index}: {last_byte}")
                if last_byte != 0x83:
                    logging.error(f"Incorrect SigHash type at input {index}")
                    return False, "One or more inputs do not use the required SigHash type SINGLE | ANYONECANPAY."
            
            else:
                logging.error("Missing or invalid witness data")
                return False, "Witness data missing or invalid in one or more inputs."
        
        logging.info("Transaction is valid")
        return True, "Transaction is valid."
    except Exception as e:
        logging.exception("Error during transaction validation")
        return False, f"Error during transaction validation: {e}"

# Test the function with a sample raw transaction string
result = validate_transaction("your_raw_transaction_here")
print(result)

def main() -> None:
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    application = Application.builder().token(token).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_transaction))

    application.run_polling()

if __name__ == '__main__':
    main()

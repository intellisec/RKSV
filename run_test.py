#!/usr/bin/python3

import base64
import datetime
import json
import os
import sys

import cashreg
import depexport
import key_store
import sigsys
import utils

if __name__ == "__main__":
    if len(sys.argv) < 4 or len(sys.argv) % 2 != 0:
        print("Usage: ./run_test.py <JSON test case spec> <cert 1 priv> <cert 1> [<cert 2 priv> <cert 2>]...")
        sys.exit(0)

    tcJson = None
    with open(sys.argv[1]) as f:
        tcJson = json.loads(f.read())

    if len(sys.argv) != (tcJson['numberOfSignatureDevices'] * 2 + 2):
        print("I need keys and certificates for %d signature devices." %
                tcJson['numberOfSignatureDevices'])
        sys.exit(0)

    baseDir = tcJson['simulationRunLabel']
    if not os.path.exists(baseDir):
        os.mkdir(baseDir)

    key = base64.b64decode(tcJson['base64AesKey'])

    register = cashreg.CashRegister('AT0', tcJson['cashBoxId'], None,
            int(0.0 * 100), key)

    keyStore = key_store.KeyStore()

    sigsBroken = list()
    sigsWorking = list()
    for i in range(tcJson['numberOfSignatureDevices']):
        serial = None
        with open(sys.argv[i * 2 + 1 + 2]) as f:
            cert = f.read()
            keyStore.putPEMCert(cert)
            serial = "%x" % utils.loadCert(cert).serial

        sigB = sigsys.SignatureSystemBroken(serial)
        sigW = sigsys.SignatureSystemWorking(serial, sys.argv[i * 2 + 2])

        sigsBroken.append(sigB)
        sigsWorking.append(sigW)

    os.chdir(baseDir)

    receipts = list()
    for recI in tcJson['cashBoxInstructionList']:
        receiptId = recI['receiptIdentifier']
        dateTime = datetime.datetime.strptime(recI['dateToUse'],
                "%Y-%m-%dT%H:%M:%S")

        sumA = recI['simplifiedReceipt']['taxSetNormal']
        sumB = recI['simplifiedReceipt']['taxSetErmaessigt1']
        sumC = recI['simplifiedReceipt']['taxSetErmaessigt2']
        sumD = recI['simplifiedReceipt']['taxSetNull']
        sumE = recI['simplifiedReceipt']['taxSetBesonders']

        sig = None
        if recI['signatureDeviceDamaged']:
            sig = sigsBroken[recI['usedSignatureDevice']]
        else:
            sig = sigsWorking[recI['usedSignatureDevice']]

        dummy = False
        reversal = False
        if 'typeOfReceipt' in recI:
            if recI['typeOfReceipt'] == 'STORNO_BELEG':
                reversal = True
            if recI['typeOfReceipt'] == 'TRAINING_BELEG':
                dummy = True

        rec = register.receipt('R1', receiptId, dateTime, sumA, sumB, sumC,
                sumD, sumE, sig, dummy, reversal)
        receipts.append(rec)

    exporter = depexport.DEPExporter('R1', None)

    with open('dep-export.json', 'w') as f:
        f.write(exporter.export(receipts))

    with open('cryptographicMaterialContainer.json', 'w') as f:
        ksJson = keyStore.writeStoreToJson()
        ksJson['base64AESKey'] = tcJson['base64AesKey']
        f.write(json.dumps(ksJson, sort_keys=False, indent=2))

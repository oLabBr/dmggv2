 #!/usr/bin/env python3
 
 # Copyright (C) 2025 KikoRetroSpace (https://kikoretrospace.com.br/)
 # Save the Old Hardware!
 # Based on the Original DMGG.PY from  Vasily Galkin (galkinvv.github.io)
 
import sys, os, mmap, math, random, datetime, time
import subprocess
import argparse
import logging

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# ----------------------------------------------------- 
# CLI 
# ----------------------------------------------------- 
parser = argparse.ArgumentParser(description="AMD/ATI Memory Testing Script")

parser.add_argument('--detect', type=bool, help='Search for a Plugged ATI/AMD Cards into the System')
parser.add_argument('--test', type=bool, help='Executes the Memory Test in the Target GPU Address')
parser.add_argument('--gpu_address', type=str, help='The starting address of the GPU memory in the BUS')
parser.add_argument('--size', type=int, default=50, help='The size in MB of the test (Default: 50)')
parser.add_argument('--mem_chips', type=int, default=8, help='The number of Memory Chips in the GPU Card (Default: 8)')
parser.add_argument('--logger', type=str, help='Enables the Internal Logger')

args = parser.parse_args()

# ----------------------------------------------------
MemChipIndex = {
    "16chips" :  [
        5,
        7,
        6,
        8,
        3,
        1,
        4,
        2,
        11,
        9,
        12,
        10,
        13,
        15,
        14,
        16
    ],
    "8chips" : [        
        {
            "upper": 3,
            "lower": 2,
            "index" : [
                1,
                2
            ]
        },
        {
            "upper": 1,
            "lower": 0,
            "index": [
                3,
                4
            ]
        },
        {
            "upper": 5,
            "lower": 4,
            "index" : [
                5,
                6
            ]
        },
        {
            "upper": 7,
            "lower": 6,
            "index" : [
                7,
                8
            ]
        }
    ]
}
    
def check_sudo():
    return os.geteuid() == 0

def bin8(byte):
    return "0b{:08b}".format(byte)

# ----------------------------------------------------
# Detects all ATI/AMD VGAs in the System
# ----------------------------------------------------
def detect_cards():
    lspci_ = subprocess.Popen(['lspci', '-v'], stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()[0]
    lspci_lines = str(lspci_).split("\\n\\n")    
    detected_lines = ""
    
    for i in range(len(lspci_lines)):
        if "VGA" in lspci_lines[i] and ("AMD" in lspci_lines[i] or "ATI" in lspci_lines[i]):
            detected_lines = detected_lines + lspci_lines[i]
    
    parsed_data = detected_lines.split("\\n\\t")
    
    for i in range(len(parsed_data)):
        if "Memory" and " pref" in parsed_data[i]:
            memory_addr = parsed_data[i].split(" ")
            logging.info("Detected GPU: ")
            logging.info(" -- " + parsed_data[i])
            logging.info(" -- Possible GPU Address: " + memory_addr[2])


# ----------------------------------------------------
# Runs the Test
# ----------------------------------------------------

def test_Payload(data, phys_arr, amaifost, nbchips=8):
        global faultychips
        if len(phys_arr) > len(data):
            data += b'\x00' * (len(phys_arr) - len(data))
            
        logging.info("This test is working to detect bad chips. Warning it can give wrong faulty chip number ; only the amount of faulty chips will be good")
        logging.info("count the chips counter-clockwise from right to left with pcie near you")
        
        # - Writes into the Address
        phys_arr[:]=data
        
        # - Reads Back the Address
        data_possibly_modified = phys_arr[:]
        
        # Sleep a bit..
        time.sleep(0.5)
        
        bad_addresses = {}
        all_errors = []
        firstbadadress=0
        bad_bits = [0]*8
        
        for i in range(len(data)):
            
            # Compares the Payload with the Readed Data
            xored_error = data[i] ^ data_possibly_modified[i]
            
            if xored_error:
                logging.debug("Bad Address Detected: {i}")
                
                for chipIndex in range(nbchips):                 
                    
                 # Check if the current Address is in the Current Memory Chip
                 if i>=chipIndex*256*(1+int(i/(256*nbchips))) and i<(chipIndex+1)*256*(1+int(i/(256*nbchips))):                     
                    faultychips = faultychips + 1                    
                    
                    if nbchips > 8:
                        if(amaifost[chipIndex] == 0):
                            amaifost[chipIndex] = 1
                            chipId = MemChipIndex["16chips"][chipIndex]                            
                            logging.error("Chip {chipId} is faulty at Address: {i}")
                            break                                                                                                                   
                    elif nbchips==8:                                           
                        
                        for memIndexes in MemChipIndex["8chips"]:
                            if( 
                               (chipIndex==memIndexes['lower'] and amaifost[chipIndex]==0) or
                               (chipIndex==memIndexes['upper'] and amaifost[chipIndex]==0) 
                            ):
                                amaifost[chipIndex] = 1
                                chipId_lower = memIndexes["index"][0]
                                chipId_upper = memIndexes["index"][1]
                                
                                logging.error("Chip {chipId_lower} and/or {chipId_upper} is faulty at address: ${i}")                               
            
            
        if not bad_addresses:
            firstbadadress=hex(i)
            
        if xored_error not in bad_addresses:
            bad_addresses[xored_error] = [0, []]
            
        bad_addresses[xored_error][0] += 1
        all_addresses = bad_addresses[xored_error][1]
        
        if 1:
            for b in range(8):
                if xored_error & (1<<b): bad_bits[b] += 1
        if 1:    
            if len(all_addresses) < 0x4000:
                all_addresses.append(i)
            if len(all_errors) < 0x4000:
                all_errors.append(i)    
        
        # Test Results
        total_errors = sum((v[0] for k, v in bad_addresses.items()))
        logging.info("Faulty Chips= ",faultychips)      
        logging.info("Total bytes tested= 4*" + str(len(data)//4))
        logging.info("Total errors count= ", total_errors, " - every ", len(data)/(total_errors+1), " OK: ", len(data) - total_errors)
            
    # ---- END
    
def run_tests(): 
    if len(args.gpu_address) < 2 or args.size < 0 or args.mem_chips < 0:
        parser.print_help()     
        return
    
    amaifost = [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]
    
    logging.info("Test Parameters: ")
    logging.info(" -- GPU Address: " + args.gpu_address)
    logging.info(" -- Payload Size: " + str(args.size) + "mb")
    logging.info(" -- Memory Chips: " + str(args.mem_chips))
    
    bytesToTest = int(1024 * 1024 * float(args.size))
    offset = int(args.gpu_address, 16)
    nbchips = args.mem_chips
    
    physmem = os.open("/dev/" + os.environ.get("MEM","mem"), os.O_RDWR, 777)
    phys_arr = mmap.mmap(physmem, bytesToTest, offset=offset)
    
    # -- Runs a Random Payload
    logging.info("-- RANDOM PAYLOAD TEST START ---")    
    data = bytes(random.getrandbits(8) for i in range(len(phys_arr)))
    test_Payload(data, phys_arr, amaifost, nbchips)                                
    logging.info("-- RANDOM PAYLOAD TEST END ---")    
    
    # ---- END
    

# ----------------------------------------------------
# Main
# ----------------------------------------------------
def main():     
    if(args.logger != None and len(args.logger) > 0):        
        logging.getLogger().addHandler(logging.FileHandler(args.logger))
        
    try:
        if not check_sudo():
            print("!!! THE TOOL NEED TO BY RUN AS ROOT !!!")   
            exit(-1)
        
        if(args.detect):
            detect_cards()
            exit(0)
            
        if(args.test):
            exit(0)
    except Exception as err:
        logging.error(f"[ERROR] Failed to execute the script: {err=}")

main()
    
    
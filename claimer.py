import hashlib, os, struct, sys, socket, time, urllib2, json, argparse, cStringIO, traceback, hmac

N = 0xfffffffffffffffffffffffffffffffffffffffffffffffffffffffefffffc2fL
R = 0xfffffffffffffffffffffffffffffffebaaedce6af48a03bbfd25e8cd0364141L
A = 0L
B = 7L
gx = 0x79be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798L
gy = 0x483ada7726a3c4655da4fbfc0e1108a8fd17b448a68554199c47d08ffb10d4b8L

def doublesha(s):
    s = hashlib.sha256(s).digest()
    return hashlib.sha256(s).digest()

def lengthprefixed(s):
    return make_varint(len(s)) + s

def read_varint(st):
    value = ord(st.read(1))
    if value < 0xfd:
        return value
    if value == 0xfd:
        return struct.unpack("<H", st.read(2))[0]
    if value == 0xfe:
        return struct.unpack("<L", st.read(4))[0]
    if value == 0xff:
        return struct.unpack("<Q", st.read(8))[0]
        
def make_varint(value):
    if value < 0xfd:
        return chr(value)
    if value <= 0xffff:
        return "\xfd" + struct.pack("<H", value)
    if value <= 0xffffffff:
        return "\xfe" + struct.pack("<L", value)
    
    return "\xff" + struct.pack("<Q", value)
    
def get_consent(consentstring):
    print "Write '%s' to continue" % consentstring

    answer = raw_input()
    if answer != consentstring:
        raise Exception("User did not write '%s', aborting" % consentstring)

def recv_all(s, length):
    ret = ""
    while len(ret) < length:
        temp = s.recv(length - len(ret))
        if len(temp) == 0:
            raise socket.error("Connection reset!")
        ret += temp
        
    return ret
    
class Client(object):
    def __init__(self, coin):
        self.coin = coin
        
    def send(self, cmd, msg):
        magic = struct.pack("<L", coin.magic)
        wrapper = magic + cmd.ljust(12, "\x00") + struct.pack("<L", len(msg)) + hashlib.sha256(hashlib.sha256(msg).digest()).digest()[0:4] + msg
        self.sc.sendall(wrapper)
        print "sent", repr(cmd)
        
    def recv_msg(self):
        header = recv_all(self.sc, 24)
        
        if len(header) != 24:
            print "INVALID HEADER LENGTH", repr(head)
            exit()

        cmd = header[4:16].rstrip("\x00")
        payloadlen = struct.unpack("<I", header[16:20])[0]
        payload = recv_all(self.sc, payloadlen)
        return cmd, payload
        
    def send_tx(self, txhash, tx):
        serverindex = ord(os.urandom(1)) % len(coin.seeds)
        while True:
            try:
                address = (coin.seeds[serverindex], coin.port)
                print "trying to connect to", address
                self.sc = socket.create_connection(address)
                print "connected to", address

                services = 0
                localaddr = "\x00" * 8 + "00000000000000000000FFFF".decode("hex") + "\x00" * 6
                nonce = os.urandom(8)
                user_agent = "Scraper"
                msg = struct.pack("<IQQ", coin.versionno, services, int(time.time())) + localaddr + localaddr + nonce + lengthprefixed(user_agent) + struct.pack("<IB", 0, 0)
                client.send("version", msg)

                while True:
                    cmd, payload = client.recv_msg()
                    print "received", cmd, "size", len(payload)
                    if cmd == "version":
                        client.send("verack", "")
                        
                    elif cmd == "sendheaders":
                        msg = make_varint(0)
                        client.send("headers", msg)
                        
                    elif cmd == "ping":
                        client.send("pong", payload)
                        client.send("inv", "\x01" + struct.pack("<I", 1) + txhash)
                        client.send("mempool", "")
                        #client.send("getaddr", "")
                        
                    elif cmd == "getdata":
                        if payload == "\x01\x01\x00\x00\x00" + txhash:
                            print "sending txhash"
                            client.send("tx", tx)
                         
                    elif cmd == "feefilter":
                        minfee = struct.unpack("<Q", payload)[0]
                        print "server requires minimum fee of %d satoshis" % minfee
                            
                    elif cmd == "inv":
                        blocks_to_get = []
                        st = cStringIO.StringIO(payload)
                        ninv = read_varint(st)
                        for i in xrange(ninv):
                            invtype = struct.unpack("<I", st.read(4))[0]
                            invhash = st.read(32)
                            
                            if invtype == 1:
                                if invhash == txhash:
                                    print "OUR TRANSACTION IS IN THEIR MEMPOOL, TRANSACTION ACCEPTED! YAY!"
                                    print "TX ID: %s", % txhash
                            elif invtype == 2:
                                blocks_to_get.append(invhash)
                                print "New block observed", invhash[::-1].encode("hex")
                                
                        if len(blocks_to_get) > 0:
                            inv = ["\x02\x00\x00\x00" + invhash for invhash in blocks_to_get]
                            msg = make_varint(len(inv)) + "".join(inv)
                            client.send("getdata", msg)
                        
                    elif cmd == "block":
                        if tx in payload or plaintx in payload:
                            print "BLOCK WITH OUR TRANSACTION OBSERVED! YES!"
                            
                    elif cmd == "addr":
                        st = cStringIO.StringIO(payload)
                        naddr = read_varint(st)
                        for i in xrange(naddr):
                            data = st.read(30)
                            if data[12:24] == "\x00" * 10 + "\xff\xff":
                                print "got peer ipv4 address %d.%d.%d.%d port %d" % struct.unpack(">BBBBH", data[24:30])
                            else:
                                print "got peer ipv6 address %04x:%04x:%04x:%04x:%04x:%04x:%04x:%04x port %d" % struct.unpack(">HHHHHHHHH", data[12:30])
                        
                    else:
                        print repr(cmd), repr(payload)
                
            except (socket.error, socket.herror, socket.gaierror, socket.timeout) as e:
                traceback.print_exc()
                serverindex = (serverindex + 1) % len(coin.seeds)

    
class BitcoinFork(object):
    def __init__(self):
        self.coinratio = 1.0
        self.versionno = 70015
        self.extrabytes = ""
        self.BCDgarbage = ""
        self.txversion = 1
        
class BitcoinFaith(BitcoinFork):
    def __init__(self):
        BitcoinFork.__init__(self)
        self.ticker = "BTF"
        self.fullname = "Bitcoin Faith"
        self.hardforkheight = 500000
        self.magic = 0xe6d4e2fa
        self.port = 8346
        self.seeds = ("a.btf.hjy.cc", "b.btf.hjy.cc", "c.btf.hjy.cc", "d.btf.hjy.cc", "e.btf.hjy.cc", "f.btf.hjy.cc")
        self.signtype = 0x41
        self.signid = self.signtype | (70 << 8)
        self.PUBKEY_ADDRESS = chr(36)
        self.SCRIPT_ADDRESS = chr(40)

class BitcoinWorld(BitcoinFork):
    def __init__(self):
        BitcoinFork.__init__(self)
        self.ticker = "BTW"
        self.fullname = "Bitcoin World"
        self.hardforkheight = 499777
        self.magic = 0x777462f8
        self.port = 8357
        self.seeds = ("47.52.250.221", "47.91.237.5")
        self.signtype = 0x41
        self.signid = self.signtype | (87 << 8)
        self.PUBKEY_ADDRESS = chr(73)
        self.SCRIPT_ADDRESS = chr(31)
        self.coinratio = 10000.0

class BitcoinGold(BitcoinFork):
    def __init__(self):
        BitcoinFork.__init__(self)
        self.ticker = "BTG"
        self.fullname = "Bitcoin Gold"
        self.hardforkheight = 491407
        self.magic = 0x446d47e1
        self.port = 8338
        self.seeds = ("pool-us.bloxstor.com", "btgminingusa.com", "btg1.stage.bitsane.com", "eu-dnsseed.bitcoingold-official.org", "dnsseed.bitcoingold.org", "dnsseed.btcgpu.org")
        self.signtype = 0x41
        self.signid = self.signtype | (79 << 8)
        self.PUBKEY_ADDRESS = chr(38)
        self.SCRIPT_ADDRESS = chr(23)

class BitcoinX(BitcoinFork):
    def __init__(self):
        BitcoinFork.__init__(self)
        self.ticker = "BCX"
        self.fullname = "BitcoinX"
        self.hardforkheight = 498888
        self.magic = 0xf9bc0511
        self.port = 9003
        self.seeds = ("192.169.227.48", "120.92.119.221", "120.92.89.254", "120.131.5.173", "120.92.117.145", "192.169.153.174", "192.169.154.185", "166.227.117.163")
        self.signtype = 0x11
        self.signid = self.signtype
        self.PUBKEY_ADDRESS = chr(75)
        self.SCRIPT_ADDRESS = chr(63)
        self.coinratio = 10000.0

class Bitcoin2X(BitcoinFork):
    def __init__(self):
        BitcoinFork.__init__(self)
        self.ticker = "B2X"
        self.fullname = "Bitcoin 2X Segwit"
        self.hardforkheight = 501451
        self.magic = 0xd8b5b2f4
        self.port = 8333
        self.seeds = ("node1.b2x-segwit.io", "node2.b2x-segwit.io", "node3.b2x-segwit.io", "136.243.147.159", "136.243.171.156", "46.229.165.141", "178.32.3.12")
        self.signtype = 0x21
        self.signid = self.signtype
        self.PUBKEY_ADDRESS = chr(0)
        self.SCRIPT_ADDRESS = chr(5)
        self.versionno = 70015 | (1 << 27)

class UnitedBitcoin(BitcoinFork):
    def __init__(self):
        BitcoinFork.__init__(self)
        self.ticker = "UBTC"
        self.fullname = "United Bitcoin"
        self.hardforkheight = 498777
        self.magic = 0xd9b4bef9
        self.port = 8333
        self.seeds = ("urlelcm1.ub.com", "urlelcm2.ub.com", "urlelcm3.ub.com", "urlelcm4.ub.com", "urlelcm5.ub.com", "urlelcm6.ub.com", "urlelcm7.ub.com", "urlelcm8.ub.com", "urlelcm9.ub.com", "urlelcm10.ub.com")
        self.signtype = 0x09
        self.signid = self.signtype
        self.PUBKEY_ADDRESS = chr(0)
        self.SCRIPT_ADDRESS = chr(5)
        self.versionno = 731800
        self.extrabytes = "\x02ub"

class SuperBitcoin(BitcoinFork):
    def __init__(self):
        BitcoinFork.__init__(self)
        self.ticker = "SBTC"
        self.fullname = "Super Bitcoin"
        self.hardforkheight = 498888
        self.magic = 0xd9b4bef9
        self.port = 8334
        self.seeds = ("seed.superbtca.com", "seed.superbtca.info", "seed.superbtc.org")
        self.signtype = 0x41
        self.signid = self.signtype
        self.PUBKEY_ADDRESS = chr(0)
        self.SCRIPT_ADDRESS = chr(5)
        self.extrabytes = lengthprefixed("sbtc")
        
class BitcoinDiamond(BitcoinFork):
    def __init__(self):
        BitcoinFork.__init__(self)
        self.ticker = "BCD"
        self.fullname = "Bitcoin Diamond"
        self.hardforkheight = 495866
        self.magic = 0xd9b4debd
        self.port = 7117
        self.seeds = ("seed1.dns.btcd.io", "seed2.dns.btcd.io", "seed3.dns.btcd.io", "seed4.dns.btcd.io", "seed5.dns.btcd.io", "seed6.dns.btcd.io")
        self.signtype = 0x01
        self.signid = self.signtype
        self.PUBKEY_ADDRESS = chr(0)
        self.SCRIPT_ADDRESS = chr(5)
        self.txversion = 12
        self.BCDgarbage = "\xff" * 32
        self.coinratio = 10.0
        
class BitcoinPizza(BitcoinFork):
    def __init__(self):
        BitcoinFork.__init__(self)
        self.ticker = "BPA"
        self.fullname = "Bitcoin Pizza"
        self.hardforkheight = 501888
        self.magic = 0xd9c4bea9
        self.port = 8888
        self.seeds = ("dnsseed.bitcoinpizza.cc", "seed1.bitcoinpizza.cc", "seed2.bitcoinpizza.cc", "seed3.bitcoinpizza.cc", "seed4.bitcoinpizza.cc")
        self.signtype = 0x21
        self.signid = self.signtype | (47 << 8)
        self.PUBKEY_ADDRESS = chr(55)
        self.SCRIPT_ADDRESS = chr(80)

class BitcoinNew(BitcoinFork):
    def __init__(self):
        BitcoinFork.__init__(self)
        self.ticker = "BTN"
        self.fullname = "Bitcoin New"
        self.hardforkheight = 501000
        self.magic = 0x344d37a1
        self.port = 8838
        self.seeds = ("dnsseed.bitcoin-new.org",)
        self.signtype = 0x41
        self.signid = self.signtype | (88 << 8)
        self.PUBKEY_ADDRESS = chr(0)
        self.SCRIPT_ADDRESS = chr(5)

class BitcoinHot(BitcoinFork):
    def __init__(self):
        BitcoinFork.__init__(self)
        self.ticker = "BTH"
        self.fullname = "Bitcoin Hot"
        self.hardforkheight = 498848
        self.magic = 0x04ad77d1
        self.port = 8222
        self.seeds = ("seed-us.bitcoinhot.co", "seed-jp.bitcoinhot.co", "seed-hk.bitcoinhot.co", "seed-uk.bitcoinhot.co", "seed-cn.bitcoinhot.co")
        self.signtype = 0x41
        self.signid = self.signtype | (53 << 8)
        self.PUBKEY_ADDRESS = chr(40)
        self.SCRIPT_ADDRESS = chr(5) # NOT CERTAIN
        self.versionno = 70016
        self.coinratio = 100.0

parser = argparse.ArgumentParser()
parser.add_argument("cointicker", help="Coin type", choices=["BTF", "BTW", "BTG", "BCX", "B2X", "UBTC", "SBTC", "BCD", "BPA", "BTN", "BTH"])
parser.add_argument("txhex", help="Raw transaction to broadcast")

args = parser.parse_args()

if args.cointicker == "BTF":
    coin = BitcoinFaith()
if args.cointicker == "BTW":
    coin = BitcoinWorld()
if args.cointicker == "BTG":
    coin = BitcoinGold()
if args.cointicker == "BCX":
    coin = BitcoinX()
if args.cointicker == "B2X":
    coin = Bitcoin2X()
if args.cointicker == "UBTC":
    coin = UnitedBitcoin()
if args.cointicker == "SBTC":
    coin = SuperBitcoin()
if args.cointicker == "BCD":
    coin = BitcoinDiamond()
if args.cointicker == "BPA":
    coin = BitcoinPizza()
if args.cointicker == "BTN":
    coin = BitcoinNew()
if args.cointicker == "BTH":
    coin = BitcoinHot()

tx = args.txhex.decode("hex")
txhash = doublesha(tx)

print "Raw transaction"
print tx.encode("hex")
print

print "YOU ARE ABOUT TO SEND"

get_consent("I am sending coins on the %s network and I accept the risks" % coin.fullname)

print "generated transaction", txhash[::-1].encode("hex")
print "\n\nConnecting to servers and pushing transaction\nPlease wait for a minute before stopping the script to see if it entered the server mempool.\n\n"

client = Client(coin)
client.send_tx(txhash, tx)

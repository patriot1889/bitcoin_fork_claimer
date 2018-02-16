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
    
    _MAX_MEMPOOL_CHECKS = 5
    _MAX_CONNECTION_RETRIES = 100
    
    def __init__(self, coin):
        self.coin = coin
        self._transaction_sent = False
        self._transaction_accepted = None
        self._mempool_check_count = 0
        self._connection_retries = 0
        
    def send(self, cmd, msg):
        magic = struct.pack("<L", self.coin.magic)
        wrapper = magic + cmd.ljust(12, "\x00") + struct.pack("<L", len(msg)) + hashlib.sha256(hashlib.sha256(msg).digest()).digest()[0:4] + msg
        self.sc.sendall(wrapper)
        print "---> %s (%d bytes)" % (repr(cmd), len(msg))
        
    def recv_msg(self):
        def recv_all(length):
            ret = ""
            while len(ret) < length:
                temp = self.sc.recv(length - len(ret))
                if len(temp) == 0:
                    raise socket.error("Connection reset!")
                ret += temp
            return ret

        header = recv_all(24)
        if len(header) != 24:
            raise Exception("INVALID HEADER LENGTH\n%s" % repr(header))

        cmd = header[4:16].rstrip("\x00")
        payloadlen = struct.unpack("<I", header[16:20])[0]
        payload = recv_all(payloadlen)
        return cmd, payload
        
    def send_tx(self, txhash, tx):
        serverindex = ord(os.urandom(1)) % len(self.coin.seeds)
        txhash_hexfmt = txhash[::-1].encode("hex")
        while True:
            try:
                address = (coin.seeds[serverindex], self.coin.port)
                print "Connecting to", address, "...",
                self.sc = socket.create_connection(address, 10)
                print "SUCCESS!"
                self.sc.settimeout(120)
                
                services = 0
                localaddr = "\x00" * 8 + "00000000000000000000FFFF".decode("hex") + "\x00" * 6
                nonce = os.urandom(8)
                user_agent = "Scraper"
                msg = struct.pack("<IQQ", self.coin.versionno, services, int(time.time())) + (
                    localaddr + localaddr + nonce + lengthprefixed(user_agent) + struct.pack("<IB", 0, 0))
                client.send("version", msg)

                while True:
                    cmd, payload = client.recv_msg()
                    print "<--- '%s' (%d bytes)" % (cmd, len(payload))
                    if cmd == "version":
                        client.send("verack", "")
                        
                    elif cmd == "sendheaders":
                        msg = make_varint(0)
                        client.send("headers", msg)
                        
                    elif cmd == "ping":
                        client.send("pong", payload)

                        if not self._transaction_sent:
                            client.send("inv", "\x01" + struct.pack("<I", 1) + txhash)
                        elif not self._transaction_accepted:
                            client.send("tx", tx)
                            print "\tRe-sent transaction: %s" % txhash_hexfmt

                        client.send("mempool", "")
                        
                    elif cmd == "getdata":
                        if payload == "\x01\x01\x00\x00\x00" + txhash:
                            print "\tPeer requesting transaction details for %s" % txhash_hexfmt
                            client.send("tx", tx)
                            print "\tSENT TRANSACTION: %s" % txhash_hexfmt
                            self._transaction_sent = True

                        # If a getdata comes in without our txhash, it generally means the tx was rejected.
                        elif self._transaction_sent:
                            print "\tReceived getdata without our txhash. The transaction may have been rejected."
                            print "\tThis script will retransmit the transaction and monitor the mempool for a few minutes before giving up."
                         
                    elif cmd == "feefilter":
                        minfee = struct.unpack("<Q", payload)[0]
                        print "\tServer requires minimum fee of %d satoshis" % minfee
                        print "\tYour fee may be too small."
                            
                    elif cmd == "inv":
                        blocks_to_get = []
                        st = cStringIO.StringIO(payload)
                        ninv = read_varint(st)
                        transaction_found = False
                        invtypes = {1: 'transaction', 2: 'block'}
                        for i in xrange(ninv):
                            invtype = struct.unpack("<I", st.read(4))[0]
                            invhash = st.read(32)
                            invtypestr = invtypes[invtype] if invtype in invtypes else str(invtype)

                            if i < 10:
                                print "\t%s: %s" % (invtypestr, invhash[::-1].encode("hex"))
                            elif i == 10:
                                print "\t..."
                                print "\tNot printing additional %d transactions" % (ninv - i)
                            
                            if invtype == 1:
                                if invhash == txhash:
                                    transaction_found = True
                            elif invtype == 2:
                                blocks_to_get.append(invhash)
                        if transaction_found and not self._transaction_accepted:        
                            print "\n\tOUR TRANSACTION IS IN THEIR MEMPOOL, TRANSACTION ACCEPTED! YAY!"
                            print "\tTX ID: ", txhash[::-1].encode("hex")
                            print "\tConsider leaving this script running until it detects the transaction in a block."
                            self._transaction_accepted = True
                        elif transaction_found:
                            print "\tTransaction still in mempool. Continue waiting for block inclusion."
                        elif not blocks_to_get:
                            print "\n\tOur transaction was not found in the mempool."
                            self._mempool_check_count += 1
                            if self._mempool_check_count <= self._MAX_MEMPOOL_CHECKS:
                                print "\tWill retransmit and check again %d more times." % (self._MAX_MEMPOOL_CHECKS - self._mempool_check_count)
                            else:
                                raise Exception("\tGiving up on transaction. Please verify that the inputs have not already been spent.")

                        if blocks_to_get:
                            inv = ["\x02\x00\x00\x00" + invhash for invhash in blocks_to_get]
                            msg = make_varint(len(inv)) + "".join(inv)
                            client.send("getdata", msg)
                            print "\trequesting %d blocks" % len(blocks_to_get)
                        
                    elif cmd == "block":
                        if tx in payload or txhash in payload:
                            print "\tBLOCK WITH OUR TRANSACTION OBSERVED! YES!"
                            print "\tYour coins have been successfully sent. Exiting..."
                            return
                        else:
                            print "\tTransaction not included in observed block."
                            
                    elif cmd == "addr":
                        st = cStringIO.StringIO(payload)
                        naddr = read_varint(st)
                        for _ in xrange(naddr):
                            data = st.read(30)
                            if data[12:24] == "\x00" * 10 + "\xff\xff":
                                address = "%d.%d.%d.%d:%d" % struct.unpack(">BBBBH", data[24:30])
                            else:
                                address = "[%04x:%04x:%04x:%04x:%04x:%04x:%04x:%04x]:%d" % struct.unpack(">HHHHHHHHH", data[12:30])
                            print "\tGot peer address: %s" % address
                    elif cmd not in ('sendcmpct', 'verack'):
                        print repr(cmd), repr(payload)
                
            except (socket.error, socket.herror, socket.gaierror, socket.timeout) as e:
                if self._connection_retries >= self._MAX_CONNECTION_RETRIES:
                    raise
                print "\tConnection failed with: %s" % repr(e)
                print "\tWill retry %d more times." % (self._MAX_CONNECTION_RETRIES - self._connection_retries)
                serverindex = (serverindex + 1) % len(self.coin.seeds)
                self._connection_retries += 1
                time.sleep(2)

    
class BitcoinFork(object):
    def __init__(self):
        self.coinratio = 1.0
        self.versionno = 70015
        self.extrabytes = ""
        self.BCDgarbage = ""
        self.txversion = 1
        self.signtype = 0x01
        self.signid = self.signtype
        self.PUBKEY_ADDRESS = chr(0)
        self.SCRIPT_ADDRESS = chr(5)
        self.bch_fork = False
        
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

# https://github.com/bitcoinvote/bitcoin
class BitcoinVote(BitcoinFork):
    def __init__(self):
        BitcoinFork.__init__(self)
        self.ticker = "BTV"
        self.fullname = "Bitcoin Vote"
        self.hardforkheight = 505050
        self.magic = 0x505050f9
        self.port = 8333
        self.seeds = ("seed1.bitvote.one", "seed2.bitvote.one", "seed3.bitvote.one")
        self.signtype = 0x41
        self.signid = self.signtype | (50 << 8)

class BitcoinTop(BitcoinFork):
    def __init__(self):
        BitcoinFork.__init__(self)
        self.ticker = "BTT"
        self.fullname = "Bitcoin Top"
        self.hardforkheight = 501118
        self.magic = 0xd0b4bef9
        self.port = 18888
        self.seeds = ("dnsseed.bitcointop.org", "seed.bitcointop.org", "worldseed.bitcointop.org", "dnsseed.bitcointop.group", "seed.bitcointop.group",
            "worldseed.bitcointop.group", "dnsseed.bitcointop.club", "seed.bitcointop.club", "worldseed.bitcointop.club")
        self.signtype = 0x01
        self.signid = self.signtype
        self.txversion = 13
        self.BCDgarbage = "\xff" * 32

class BitCore(BitcoinFork):
    def __init__(self):
        BitcoinFork.__init__(self)
        self.ticker = "BTX"
        self.fullname = "BitCore"
        self.hardforkheight = 492820
        self.magic = 0xd9b4bef9
        self.port = 8555
        self.seeds = ("37.120.190.76", "37.120.186.85", "185.194.140.60", "188.71.223.206", "185.194.142.122")
        self.signtype = 0x01
        self.signid = self.signtype
        
class BitcoinPay(BitcoinFork):
    def __init__(self):
        BitcoinFork.__init__(self)
        self.ticker = "BTP"
        self.fullname = "Bitcoin Pay"
        self.hardforkheight = 499345
        self.signtype = 0x41
        self.signid = self.signtype | (80 << 8)
        self.PUBKEY_ADDRESS = chr(0x38)
        self.SCRIPT_ADDRESS = chr(5) # NOT CERTAIN
        self.coinratio = 10.0

# https://github.com/btcking/btcking
class BitcoinKing(BitcoinFork):
    def __init__(self):
        BitcoinFork.__init__(self)
        self.ticker = "BCK"
        self.fullname = "Bitcoin King"
        self.hardforkheight = 499999
        self.magic = 0x161632af
        self.port = 16333
        self.seeds = ("47.52.28.49",)
        self.signtype = 0x41
        self.signid = self.signtype | (143 << 8)
        
# https://github.com/bitcoincandyofficial/bitcoincandy
class BitcoinCandy(BitcoinFork):
    def __init__(self):
        BitcoinFork.__init__(self)
        self.ticker = "CDY"
        self.fullname = "Bitcoin Candy"
        self.hardforkheight = 512666
        self.magic = 0xd9c4c3e3
        self.port = 8367
        self.seeds = ("seed.bitcoincandy.one", "seed.cdy.one")
        self.signtype = 0x41
        self.signid = self.signtype | (111 << 8)
        self.PUBKEY_ADDRESS = chr(0x1c)
        self.SCRIPT_ADDRESS = chr(0x58)
        self.coinratio = 1000.0

# https://github.com/BTSQ/BitcoinCommunity
class BitcoinCommunity(BitcoinFork):
    def __init__(self):
        BitcoinFork.__init__(self)
        self.ticker = "BTSQ"
        self.fullname = "Bitcoin Community"
        self.hardforkheight = 506066
        self.magic = 0xd9c4ceb9
        self.port = 8866
        self.seeds = ("dnsseed.aliyinke.com", "seed1.aliyinke.com", "seed2.aliyinke.com", "seed3.aliyinke.com")
        self.signtype = 0x11
        self.signid = self.signtype | (31 << 8)
        self.PUBKEY_ADDRESS = chr(63)
        self.SCRIPT_ADDRESS = chr(58)
        self.coinratio = 1000.0

# https://github.com/worldbitcoin/worldbitcoin
class WorldBitcoin(BitcoinFork):
    def __init__(self):
        BitcoinFork.__init__(self)
        self.ticker = "WBTC"
        self.fullname = "World Bitcoin"
        self.hardforkheight = 503888
        self.magic = 0xd9b4bef9
        self.port = 8338
        self.seeds = ("dnsseed.btcteams.net", "dnsseed.wbtcteam.org")
        self.signtype = 0x41
        self.signid = self.signtype
        self.extrabytes = lengthprefixed("wbtc")
        self.coinratio = 100.0
        
# https://github.com/Bitcoin-ABC/bitcoin-abc
class BitcoinCash(BitcoinFork):
    def __init__(self):
        BitcoinFork.__init__(self)
        self.ticker = "BCH"
        self.fullname = "Bitcoin Cash"
        self.hardforkheight = 478559
        self.magic = 0xe8f3e1e3
        self.port = 8333
        self.seeds = ("seed.bitcoinabc.org", "seed-abc.bitcoinforks.org", "seed.bitprim.org", "seed.deadalnix.me", "seeder.criptolayer.net")
        self.signtype = 0x41
        self.signid = self.signtype

parser = argparse.ArgumentParser()
parser.add_argument("cointicker", help="Coin type", choices=["BTF", "BTW", "BTG", "BCX", "B2X", "UBTC", "SBTC", "BCD", "BPA", "BTN", "BTH", "BTV", "BTT", "BTX", "BTP", "BCK", "CDY", "BTSQ", "WBTC", "BCH"])
parser.add_argument("txhex", help="Raw transaction to broadcast")

args = parser.parse_args()

if args.cointicker == "B2X":
    coin = Bitcoin2X()
elif args.cointicker == "BCD":
    coin = BitcoinDiamond()
elif args.cointicker == "BCH":
    coin = BitcoinCash()
elif args.cointicker == "BCK":
    coin = BitcoinKing()
elif args.cointicker == "BCX":
    coin = BitcoinX()
elif args.cointicker == "BPA":
    coin = BitcoinPizza()
elif args.cointicker == "BTF":
    coin = BitcoinFaith()
elif args.cointicker == "BTG":
    coin = BitcoinGold()
elif args.cointicker == "BTH":
    coin = BitcoinHot()
elif args.cointicker == "BTN":
    coin = BitcoinNew()
elif args.cointicker == "BTP":
    coin = BitcoinPay()
elif args.cointicker == "BTSQ":
    coin = BitcoinCommunity()
elif args.cointicker == "BTT":
    coin = BitcoinTop()
elif args.cointicker == "BTV":
    coin = BitcoinVote()
elif args.cointicker == "BTW":
    coin = BitcoinWorld()
elif args.cointicker == "BTX":
    coin = BitCore()
elif args.cointicker == "CDY":
    coin = BitcoinCandy()
elif args.cointicker == "SBTC":
    coin = SuperBitcoin()
elif args.cointicker == "UBTC":
    coin = UnitedBitcoin()
elif args.cointicker == "WBTC":
    coin = WorldBitcoin()

tx = args.txhex.decode("hex")
txhash = doublesha(tx)

print

print "YOU ARE ABOUT TO SEND"

get_consent("send it")

print "TX ID: ", txhash[::-1].encode("hex")
print "\n\nConnecting to servers and pushing transaction\nPlease wait for a minute before stopping the script to see if it entered the server mempool.\n\n"

client = Client(coin)
client.send_tx(txhash, tx)

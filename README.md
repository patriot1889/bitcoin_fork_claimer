This is a small script that enables you to transfer/claim various coins in Bitcoin forks
without downloading the full blockchains or messing with the official clients.

Requires Python 2.7

This fork only supports the broadcasting of signed raw transactions. (such as made using the clients, useful for broadcasting multisig transactions)

The following coins are recognized, although may not be fully tested:

*  B2X - [Segwit 2X](https://b2x-segwit.io/)
*  BCD - [Bitcoin Diamond](http://www.btcd.io/)
*  BCH - [Bitcoin Cash](https://www.bitcoincash.org/)
*  BCK - [Bitcoin King](https://btcking.org/) - NOT A TRUE FORK, NOT CLAIMABLE AT THE MOMENT
*  BCX - [Bitcoin X](https://bcx.org/)
*  BPA - [Bitcoin Pizza](http://p.top/en/index.html)
*  BTF - [Bitcoin Faith](http://bitcoinfaith.org/)
*  BTG - [Bitcoin Gold](https://bitcoingold.org/)
*  BTH - [Bitcoin Hot](https://www.bithot.org/)
*  BTN - [Bitcoin New](http://btn.kim/)
*  BTP - [Bitcoin Pay](http://www.btceasypay.com/)
*  BTSQ - [Bitcoin Community](http://btsq.top/)
*  BTT - [Bitcoin Top](https://bitcointop.org/)
*  BTV - [Bitcoin Vote](https://bitvote.one/)
*  BTW - [Bitcoin World](http://www.btw.one/)
*  BTX - [Bitcore](https://bitcore.cc/)
*  CDY - [Bitcoin Candy](https://cdy.one/) - Forked from Bitcoin Cash, not Bitcoin
*  SBTC - [Super Bitcoin](http://superbtc.org/)
*  UBTC - [United Bitcoin](https://www.ub.com/)
*  WBTC - [World Bitcoin](http://www.wbtcteam.org/)

Usage of this script is not risky. However, creating raw transactions can be. Please make sure you are using the correct send addresses and fees.

    claimer.py <cointype> <signedtxhex>

#!/bin/bash
# -*- coding: utf-8 -*-
# Sample script to GPG sign Release files
# Copyright © 2002 Colin Walters <walters@debian.org>

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

# Usage:

# You need to create a secret keyring (secring.gpg).  You can use your
# existing one, or create a new one by doing something like the
# following:

# $ GNUPGHOME=/src/debian/mini-dinstall/s3kr1t gnupg --gen-key

set -e

# Initialize GPG
gpg --help 1>/dev/null 2>&1 || true

rm -f Release.gpg.tmp
gpg --batch --default-key "${SIGNKEY}" --detach-sign -o Release.gpg.tmp "$1"
mv Release.gpg.tmp Release.gpg

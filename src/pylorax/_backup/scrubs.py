    def __setBusyboxLinks(self):
        src = os.path.join(self.destdir, 'sbin', 'busybox.anaconda')
        dst = os.path.join(self.destdir, 'bin', 'busybox')
        mv(src, dst)

        cwd = os.getcwd()
        os.chdir(os.path.join(self.destdir, 'bin'))

        busybox_process = subprocess.Popen(['./busybox'], stdout=subprocess.PIPE)
        busybox_process.wait()

        if busybox_process.returncode:
            raise Error, 'busybox error'
        
        busybox_output = busybox_process.stdout.readlines()
        busybox_output = map(lambda line: line.strip(), busybox_output)
        busybox_output = busybox_output[busybox_output.index('Currently defined functions:') + 1:]

        commands = []
        for line in busybox_output:
            commands.extend(map(lambda c: c.strip(), line.split(',')))

        # remove empty strings
        commands = filter(lambda c: c, commands)

        for command in commands:
            # XXX why do we skip these commands? can "busybox" be there at all?
            if command not in ['buxybox', 'sh', 'shutdown', 'poweroff', 'reboot']:
                if not os.path.exists(command):
                    os.symlink('busybox', command)

        os.chdir(cwd)

    def __strip(self):
        # XXX is this thing really needed? it's ugly
        fnames = map(lambda fname: os.path.join(self.destdir, fname), os.listdir(self.destdir))
        fnames = filter(lambda fname: os.path.isfile(fname), fnames)

        executables = []
        xmodules = os.path.join('usr', 'X11R6', self.libdir, 'modules')
        for fname in fnames:
            if not fname.find(xmodules) == -1:
                continue

            mode = os.stat(fname).st_mode
            if (mode & stat.S_IXUSR):
                executables.append(fname)

        elfs = []
        for exe in executables:
            p = subprocess.Popen(['file', exe], stdout=subprocess.PIPE)
            p.wait()

            output = p.stdout.readlines()
            output = ''.join(output)
            if re.match(r'^[^:]*:.*ELF.*$', output):
                elfs.append(exe)

        for elf in elfs:
            p = subprocess.Popen(['objdump', '-h', elf], stdout=subprocess.PIPE)
            p.wait()

            cmd = ['strip']
            if self.arch == 'ia64':
                cmd.append('--strip-debug')

            arglist = [elf, '-R', '.comment', '-R', '.note']
            for line in p.stdout.readlines():
                m = re.match(r'^.*(?P<warning>\.gnu\.warning\.[^ ]*) .*$', line)
                if m:
                    arglist.extend(['-R', m.group('warning')])

            p = subprocess.Popen(cmd + arglist)
            p.wait()

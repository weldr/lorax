import re
from tito.common import run_command
from tito.tagger import VersionTagger


class LoraxRHELTagger(VersionTagger):
    """
    Tagger which is based on ReleaseTagger and use Red Hat Enterprise Linux
    format of Changelog:
    - description
      Resolves/Related: rhbz#1111

    Used for:
        - Red Hat Enterprise Linux

    If you want it put in tito.pros:
    [buildconfig]
    tagger = lorax_tito.LoraxRHELTagger
    """
    def _getCommitDetail(self, commit, field):
        """ Get specific details about the commit using git log format field specifiers.
        """
        command = ['git', 'log', '-1', "--pretty=format:%s" % field, commit]
        output = run_command(" ".join(command))
        ret = output.strip('\n').split('\n')

        if len(ret) == 1 and ret[0].find('@') != -1:
            ret = [ret[0].split('@')[0]]
        elif len(ret) == 1:
            ret = [ret[0]]
        else:
            ret = [x for x in ret if x != '']

        return ret

    def _generate_default_changelog(self, last_tag):
        """
        Run git-log and will generate changelog, which still can be edited by user
        in _make_changelog.
        use format:
        - description
          Resolves/Related: rhbz#1111
        """
        patch_command = "git log --pretty=oneline --relative %s..%s -- %s" % (last_tag, "HEAD", ".")
        output = filter(lambda x: x.find('l10n: ') != 41 and \
                                  x.find('Merge commit') != 41 and \
                                  x.find('Merge branch') != 41,
                        run_command(patch_command).strip('\n').split('\n'))

        rpm_log = []
        for line in output:
            if not line:
                continue

            rhbz = set()
            commit = line.split(' ')[0]
            summary = self._getCommitDetail(commit, "%s")[0]
            body = self._getCommitDetail(commit, "%b")
            author = self._getCommitDetail(commit, "%aE")[0]

            # prepend Related/Resolves if subject contains BZ number
            m = re.search(r"\(#\d+(\,.*)*\)", summary)
            if m:
                fullbug = summary[m.start():m.end()]
                bugstr = summary[m.start()+2:m.end()-1]

                bug = ''
                for c in bugstr:
                    if c.isdigit():
                        bug += c
                    else:
                        break

                if len(bugstr) > len(bug):
                    tmp = bugstr[len(bug):]

                    for c in tmp:
                        if not c.isalpha():
                            tmp = tmp[1:]
                        else:
                            break

                    if len(tmp) > 0:
                        author = tmp

                summary = summary.replace(fullbug, "(%s)" % author)
                rhbz.add("Resolves: rhbz#%s" % bug)

                summary_bug = bug
            else:
                summary = summary.strip()
                summary += " (%s)" % author
                summary_bug = None

            for bodyline in body:
                m = re.match(r"^(Resolves|Related|Conflicts):\ +rhbz#\d+.*$", bodyline)
                if not m:
                    continue

                actionre = re.search("(Resolves|Related|Conflicts)", bodyline)
                bugre = re.search(r"\d+", bodyline)
                if actionre and bugre:
                    action = actionre.group()
                    bug = bugre.group()
                    rhbz.add("%s: rhbz#%s" % (action, bug))

                    # Remove the summary bug's Resolves action if it is for the same bug
                    if action != 'Resolves':
                        summary_str = "Resolves: rhbz#%s" % summary_bug
                        if summary_bug and bug == summary_bug and summary_str in rhbz:
                            rhbz.remove(summary_str)

            if rhbz:
                rpm_log.append("%s\n%s" %(summary.strip(),"\n".join(rhbz)))
            else:
                rpm_log.append("%s (%s)" % (summary.strip(), author))

        return "\n".join(rpm_log)

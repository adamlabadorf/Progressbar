#!/usr/bin/python
# -*- coding: iso-8859-1 -*-
#
# progressbar    - Text progressbar library for python.
# Copyright (c) 2005 Nilton Volpato
# 
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
# 
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.    See the GNU
# Lesser General Public License for more details.
# 
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA    02110-1301    USA


"""Text progressbar library for python.

This library provides a text mode progressbar. This is tipically used
to display the progress of a long running operation, providing a
visual clue that processing is underway.

The ProgressBar class manages the progress, and the format of the line
is given by a number of widgets. A widget is an object that may
display diferently depending on the state of the progress. There are
three types of widget:
- a string, which always shows itself;
- a ProgressBarWidget, which may return a diferent value every time
it's update method is called; and
- a ProgressBarWidgetHFill, which is like ProgressBarWidget, except it
expands to fill the remaining width of the line.

The progressbar module is very easy to use, yet very powerful. And
automatically supports features like auto-resizing when available.
"""

__author__ = "Nilton Volpato"
__author_email__ = "first-name dot last-name @ gmail.com"
__date__ = "2006-05-07"
__version__ = "2.2"

# Changelog
#
# 2006-05-07: v2.2 fixed bug in windows
# 2005-12-04: v2.1 autodetect terminal width, added start method
# 2005-12-04: v2.0 everything is now a widget (wow!)
# 2005-12-03: v1.0 rewrite using widgets
# 2005-06-02: v0.5 rewrite
# 2004-??-??: v0.1 first version


import sys, time
from array import array
try:
    from fcntl import ioctl
    import termios
except ImportError:
    pass
import signal

class ProgressBarWidget(object):
    """This is an element of ProgressBar formatting.

    The ProgressBar object will call it's update value when an update
    is needed. It's size may change between call, but the results will
    not be good if the size changes drastically and repeatedly.
    """
    def update(self, pbar):
        """Returns the string representing the widget.

        The parameter pbar is a reference to the calling ProgressBar,
        where one can access attributes of the class for knowing how
        the update must be made.

        At least this function must be overriden."""
        pass

class ProgressBarWidgetHFill(object):
    """This is a variable width element of ProgressBar formatting.

    The ProgressBar object will call it's update value, informing the
    width this object must the made. This is like TeX \\hfill, it will
    expand to fill the line. You can use more than one in the same
    line, and they will all have the same width, and together will
    fill the line.
    """
    def update(self, pbar, width):
        """Returns the string representing the widget.

        The parameter pbar is a reference to the calling ProgressBar,
        where one can access attributes of the class for knowing how
        the update must be made. The parameter width is the total
        horizontal width the widget must have.

        At least this function must be overriden."""
        pass


class ETA(ProgressBarWidget):
    "Widget for the Estimated Time of Arrival"
    def format_time(self, seconds):
        return time.strftime('%H:%M:%S', time.gmtime(seconds))
    def update(self, pbar):
        if pbar.currval == 0:
            return 'ETA:    --:--:--'
        elif pbar.finished:
            return 'Time: %s' % self.format_time(pbar.seconds_elapsed)
        else:
            elapsed = pbar.seconds_elapsed
            eta = elapsed * pbar.maxval / pbar.currval - elapsed
            return 'ETA:    %s' % self.format_time(eta)

class FileTransferSpeed(ProgressBarWidget):
    "Widget for showing the transfer speed (useful for file transfers)."
    def __init__(self):
        self.fmt = '%6.2f %s'
        self.units = ['B','K','M','G','T','P']
    def update(self, pbar):
        if pbar.seconds_elapsed < 2e-6:#== 0:
            bps = 0.0
        else:
            bps = float(pbar.currval) / pbar.seconds_elapsed
        spd = bps
        for u in self.units:
            if spd < 1000:
                break
            spd /= 1000
        return self.fmt % (spd, u+'/s')

class RotatingMarker(ProgressBarWidget):
    "A rotating marker for filling the bar of progress."
    def __init__(self, markers='|/-\\'):
        self.markers = markers
        self.curmark = -1
    def update(self, pbar):
        if pbar.finished:
            return self.markers[0]
        self.curmark = (self.curmark + 1)%len(self.markers)
        return self.markers[self.curmark]

class Percentage(ProgressBarWidget):
    "Just the percentage done."
    def update(self, pbar):
        return '%3d%%' % pbar.percentage()

class Bar(ProgressBarWidgetHFill):
    "The bar of progress. It will strech to fill the line."
    def __init__(self, marker='#', left='|', right='|'):
        self.marker = marker
        self.left = left
        self.right = right
    def _format_marker(self, pbar):
        if isinstance(self.marker, (str, unicode)):
            return self.marker
        else:
            return self.marker.update(pbar)
    def update(self, pbar, width):
        percent = pbar.percentage()
        cwidth = width - len(self.left) - len(self.right)
        marked_width = int(percent * cwidth / 100)
        m = self._format_marker(pbar)
        bar = (self.left + (m*marked_width).ljust(cwidth) + self.right)
        return bar

class ReverseBar(Bar):
    "The reverse bar of progress, or bar of regress. :)"
    def update(self, pbar, width):
        percent = pbar.percentage()
        cwidth = width - len(self.left) - len(self.right)
        marked_width = int(percent * cwidth / 100)
        m = self._format_marker(pbar)
        bar = (self.left + (m*marked_width).rjust(cwidth) + self.right)
        return bar

class Counter(ProgressBarWidget) :

    def __init__(self) :
        self.maxval = 0
        self.currval = 0

    def update(self,pbar) :
        if self.maxval != pbar.maxval :
            self.maxval = pbar.maxval
        self.currval = pbar.currval
        return "%d / %d"%(self.currval,self.maxval)

default_widgets = [Percentage(), ' ', Bar(), ' ', Counter(),' ',ETA()]
class ProgressBar(object):
    """This is the ProgressBar class, it updates and prints the bar.

    The term_width parameter may be an integer. Or None, in which case
    it will try to guess it, if it fails it will default to 80 columns.

    The simple use is like this:
    >>> pbar = ProgressBar().start()
    >>> for i in xrange(100):
    ...    # do something
    ...    pbar.update(i+1)
    ...
    >>> pbar.finish()

    But anything you want to do is possible (well, almost anything).
    You can supply different widgets of any type in any order. And you
    can even write your own widgets! There are many widgets already
    shipped and you should experiment with them.

    When implementing a widget update method you may access any
    attribute or function of the ProgressBar object calling the
    widget's update method. The most important attributes you would
    like to access are:
    - currval: current value of the progress, 0 <= currval <= maxval
    - maxval: maximum (and final) value of the progress
    - finished: True if the bar is have finished (reached 100%), False o/w
    - start_time: first time update() method of ProgressBar was called
    - seconds_elapsed: seconds elapsed since start_time
    - percentage(): percentage of the progress (this is a method)
    """
    def __init__(self, maxval=100, widgets=default_widgets, term_width=None,
                 fd=sys.stderr, title=None):
        assert maxval > 0
        self.maxval = maxval
        self.widgets = widgets
        if title :
            self.widgets = [title]+widgets
        self.fd = fd
        self.signal_set = False
        if term_width is None:
            try:
                self.handle_resize(None,None)
                signal.signal(signal.SIGWINCH, self.handle_resize)
                self.signal_set = True
            except:
                self.term_width = 79
        else:
            self.term_width = term_width

        self.currval = 0
        self.finished = False
        self.prev_percentage = -1
        self.start_time = None
        self.seconds_elapsed = 0

    def handle_resize(self, signum, frame):
        h,w=array('h', ioctl(self.fd,termios.TIOCGWINSZ,'\0'*8))[:2]
        self.term_width = w

    def percentage(self):
        "Returns the percentage of the progress."
        return self.currval*100.0 / self.maxval

    def _format_widgets(self):
        r = []
        hfill_inds = []
        num_hfill = 0
        currwidth = 0
        for i, w in enumerate(self.widgets):
            if isinstance(w, ProgressBarWidgetHFill):
                r.append(w)
                hfill_inds.append(i)
                num_hfill += 1
            elif isinstance(w, (str, unicode)):
                r.append(w)
                currwidth += len(w)
            else:
                weval = w.update(self)
                currwidth += len(weval)
                r.append(weval)
        for iw in hfill_inds:
            r[iw] = r[iw].update(self, (self.term_width-currwidth)/num_hfill)
        return r

    def _format_line(self):
        return ''.join(self._format_widgets()).ljust(self.term_width)

    def _need_update(self):
        return self.percentage() != self.prev_percentage

    def update(self, value=None):
        "Updates the progress bar to a new value.    If no value argument is passed, progress bar is incremented by pbar.currval+1"
        self._update(value)
        if self.finished :
            self.fd.write(self._format_line() + '\n')
        else:
            self.fd.write(self._format_line() + '\r')

    def _update(self,value=None) :
        """Private method for updating progress bar without printing anything"""
        if value is None :
            value = self.currval + 1
        assert 0 <= value
        assert value <= self.maxval
        self.currval = value
        if not self._need_update() or self.finished:
            return
        if not self.start_time:
            self.start_time = time.time()
        self.seconds_elapsed = time.time() - self.start_time
        self.prev_percentage = self.percentage()

        self.finished = self.currval == self.maxval

    def start(self):
        """Start measuring time, and prints the bar at 0%.

        It returns self so you can use it like this:
        >>> pbar = ProgressBar().start()
        >>> for i in xrange(100):
        ...    # do something
        ...    pbar.update(i+1)
        ...
        >>> pbar.finish()
        """
        self.update(0)
        return self

    def finish(self):
        """Used to tell the progress is finished."""

        if not self.finished :
            self.finished = True
            self.update(self.maxval)

        if self.signal_set:
            signal.signal(signal.SIGWINCH, signal.SIG_DFL)


class MultiStageProgressBar(ProgressBar) :
    '''Wraps multiple progress bars for nested processes.  Instantiate just as
    a regular ProgressBar object except maxval and title are lists corresponding
    to the nested bars.  Update with *pbar.update(stage=n)* where *n* is the
    desired stage to advance.  Progress bars are scaled to termwidth/n unless
    explicitly set as a list passed to the constructor or with *pbar.set_stage_widths()*,
    both of which accept a list of percentages.  The same widgets are used for
    each progressbar unless explicitly set with *pbar.set_stage_widgets()*.
    stage 0 is the first stage.

    Class is NOT threadsafe.
    '''
    def __init__(self,maxvals=[100],widgets=default_widgets,term_widths=None,
                 fd=sys.stderr,titles=None,cascade=True) :

        self.maxvals = maxvals
        self.num_stages = len(maxvals)
        self.fd = fd
        self.finished = False

        # assert out titular authority bizatch
        # - or -
        # titles has to match maxvals
        if titles :
            assert len(maxvals) == len(titles)
        else :
            titles = ['']*len(maxvals)
        self.titles = titles

        # try to get the terminal width
        try:
            self.handle_resize(None,None)
            signal.signal(signal.SIGWINCH, self.handle_resize)
            self.signal_set = True
        except Exception, e :
            print e
            self.term_width = 79

        if term_widths :
            assert len(term_widths) == len(maxvals)
            assert sum(term_widths) == 1
        else :
            term_widths = [1./self.num_stages]*self.num_stages


        # correct for integer division remainders so sum(stage_widths) == term_width
        self.stage_widths = [int(self.term_width*st_w) for st_w in term_widths]
        self.stage_widths[-1] += self.term_width-sum(self.stage_widths)

        # adjust titles and widths to add a space before nested pbars
        self.titles[1:] = [' '+t for t in self.titles[1:]]
        self.stage_widths[1:] = [w-1 for w in self.stage_widths[1:]]

        self._pbars = [ProgressBar(maxval=x,title=t,term_width=w) for x,t,w in zip(self.maxvals,self.titles,self.stage_widths)]

        # when updating stage n, also reset [n+1,n+2,...,num_stages)
        self.cascade = cascade

        self.update_calls = 0

    def handle_resize(self, signum, frame):
        h,w=array('h', ioctl(self.fd,termios.TIOCGWINSZ,'\0'*8))[:2]
        self.term_width = w

    def start(self) :
        for pbar in self._pbars :
            pbar._update(0)
        return self

    def set_title(self,stage,title) :
        self.titles[stage] = title

    def reset_stage(self,stage,maxval=None,title=None) :
        if maxval :
            self.maxvals[stage] = maxval
        if title :
            self.titles[stage] = title
        self._pbars[stage] = ProgressBar(maxval=self.maxvals[stage],title=self.titles[stage],term_width=self.stage_widths[stage])
        to_reset = range(stage,self.num_stages) if self.cascade else [stage]
        for st in to_reset :
            self._pbars[st] = ProgressBar(maxval=self.maxvals[st],title=self.titles[st],term_width=self.stage_widths[st])

    def update(self,stage=None,val=None) :
        self.update_calls += 1

        # update the deepest pbar that is not already finished
        if stage is None :
            stage = self.num_stages-1

        # update this bar
        self._pbars[stage]._update()

        # incrememt the preceeding pbar if possible if this one is done
        if self._pbars[stage].finished :
            if 0 < stage < self.num_stages :
                self.reset_stage(stage)
                self.update(stage=stage-1)
            elif stage == 0 : # whole thing ha terminado
                self.finished = True
                for pbar in self._pbars :
                    pbar._update(pbar.maxval)
                self.print_bars() # the last shabang
        else :
            self.print_bars()

    def finish(self) :
        if not self.finished :
            self.finished = True
            for pbar in self._pbars :
                pbar._update(pbar.maxval-1) # -1 cuz...it's kind of a hack
            if self.signal_set:
                signal.signal(signal.SIGWINCH, signal.SIG_DFL)
            self.update()

    def print_bars(self) :
         # print out string
        out_str = ''.join([pbar._format_line() for pbar in self._pbars])
        if self.finished :
            self.fd.write(out_str+'\n')
        else :
            self.fd.write(out_str+'\r')


if __name__=='__main__':
    import os

    def example1():
        widgets = ['Test: ', Percentage(), ' ', Bar(marker=RotatingMarker()),
                     ' ', ETA(), ' ', FileTransferSpeed()]
        pbar = ProgressBar(widgets=widgets, maxval=10000000).start()
        for i in range(1000000):
            # do something
            pbar.update(10*i+1)
        pbar.finish()
        print

    def example2():
        class CrazyFileTransferSpeed(FileTransferSpeed):
            "It's bigger between 45 and 80 percent"
            def update(self, pbar):
                if 45 < pbar.percentage() < 80:
                    return 'Bigger Now ' + FileTransferSpeed.update(self,pbar)
                else:
                    return FileTransferSpeed.update(self,pbar)

        widgets = [CrazyFileTransferSpeed(),' <<<', Bar(), '>>> ', Percentage(),' ', ETA()]
        pbar = ProgressBar(widgets=widgets, maxval=10000000)
        # maybe do something
        pbar.start()
        for i in range(2000000):
            # do something
            pbar.update(5*i+1)
        pbar.finish()
        print

    def example3():
        widgets = [Bar('>'), ' ', ETA(), ' ', ReverseBar('<')]
        pbar = ProgressBar(widgets=widgets, maxval=10000000).start()
        for i in range(1000000):
            # do something
            pbar.update(10*i+1)
        pbar.finish()
        print

    def example4():
        widgets = ['Test: ', Percentage(), ' ',
                     Bar(marker='0',left='[',right=']'),
                     ' ', ETA(), ' ', FileTransferSpeed()]
        pbar = ProgressBar(widgets=widgets, maxval=500)
        pbar.start()
        for i in range(100,500+1,50):
            time.sleep(0.2)
            pbar.update(i)
        pbar.finish()
        print


    example1()
    example2()
    example3()
    example4()


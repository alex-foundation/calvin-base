# -*- coding: utf-8 -*-

# Copyright (c) 2015 Ericsson AB
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


import pytest

from calvinservices.csparser.codegen import calvin_codegen

def parse(test, source_text):
    deployable, issuetracker = calvin_codegen(source_text, test, 'local')
    errors = issuetracker.errors(sort_key='reason')
    warnings = issuetracker.warnings(sort_key='reason')

    return deployable, errors, warnings


def testCheckSimpleScript():
    script = """
    a:std.CountTimer(sleep=0.1, start=1, steps=100)
    b:io.Print()

    a.integer > b.token
    """
    result, errors, warnings = parse('inline', script)
    assert not errors

def testCheckSimpleScript2():
    script = """
    a:Foo()
    b:Bar()
    """
    result, errors, warnings = parse('inline', script)
    assert errors

def testCheckLocalComponent():
    script = """
    component Foo() -> out {
        f:std.CountTimer(sleep=0.1, start=1, steps=100)
        f.integer > .out
    }
    a:Foo()
    b:test.Sink(store_tokens=false, quiet=false, active=true)
    a.out > b.token
    """
    result, errors, warnings = parse('inline', script)
    assert not errors



def testCheckOutportConnections():
    script = """
    a:std.CountTimer(sleep=0.1, start=1, steps=100)
    b:std.CountTimer(sleep=0.1, start=1, steps=100)
    c:test.Sink(store_tokens=false, quiet=false, active=true)
    a.integer > c.token
    """
    result, errors, warnings = parse('inline', script)
    assert errors[0]['reason'] == "Actor b (std.CountTimer) is missing connection to outport 'integer'" 

def testCheckInportConnections1():
    script = """
    c:test.Sink(store_tokens=false, quiet=false, active=true)
    """
    result, errors, warnings = parse('inline', script)
    assert len(errors) == 1 
    assert errors[0]['reason'] == "Actor c (test.Sink) is missing connection to inport 'token'" 

def testCheckInportConnections2():
    script = """
    a:std.CountTimer(sleep=0.1, start=1, steps=100)
    b:std.CountTimer(sleep=0.1, start=1, steps=100)
    c:test.Sink(store_tokens=false, quiet=false, active=true)
    a.integer > c.token
    b.integer > c.token
    """
    result, errors, warnings = parse('inline', script)
    assert len(errors) == 1 
    # assert errors[0]['reason'] == "Input port 'c.token' with multiple connections ('a.integer') must have a routing port property." 
    # assert errors[1]['reason'] == "Input port 'c.token' with multiple connections ('b.integer') must have a routing port property." 


def testBadComponent1():
    script = """
    component Foo() -> out {
        a:std.CountTimer(sleep=0.1, start=1, steps=100)
        b:std.CountTimer(sleep=0.1, start=1, steps=100)
        a.integer > .out
    }
    a:Foo()
    b:test.Sink(store_tokens=false, quiet=false, active=true)
    a.out > b.token
    """
    result, errors, warnings = parse('inline', script)
    assert len(errors) == 1 
    assert errors[0]['reason'] == "Actor b (std.CountTimer) is missing connection to outport 'integer'" 

def testBadComponent2():
    script = """
    component Foo() -> out {
        a:std.CountTimer(sleep=0.1, start=1, steps=100)
        b:test.Sink(store_tokens=false, quiet=false, active=true)
        a.integer > b.token
    }
    a:Foo()
    b:test.Sink(store_tokens=false, quiet=false, active=true)
    a.out > b.token
    """
    result, errors, warnings = parse('inline', script)
    assert len(errors) == 1 
    assert errors[0]['reason'] == "Component Foo is missing connection to outport 'out'" 

def testBadComponent3():
    script = """
    component Foo() -> out {
        a:std.CountTimer(sleep=0.1, start=1, steps=100)
        a.integer > .out
        a.integer > .out
    }
    a:Foo()
    b:test.Sink(store_tokens=false, quiet=false, active=true)
    a.out > b.token
    """
    result, errors, warnings = parse('inline', script)
    assert len(errors) == 1 
    # assert errors[0]['reason'] == "Input port 'b.token' with multiple connections ('a:a.integer') must have a routing port property." 

def testBadComponent4():
    script = """
    component Foo() in -> {
        a:test.Sink(store_tokens=false, quiet=false, active=true)
    }
    b:Foo()
    a:std.CountTimer(sleep=0.1, start=1, steps=100)
    a.integer > b.in
    """
    result, errors, warnings = parse('inline', script)
    assert len(errors) == 2 
    assert errors[0]['reason'] == "Actor a (test.Sink) is missing connection to inport 'token'" 
    assert errors[1]['reason'] == "Component Foo is missing connection to inport 'in'" 

def testBadComponent5():
    script = """
    component Foo() in -> {
        a:test.Sink(store_tokens=false, quiet=false, active=true)
        .foo > a.token
    }
    b:Foo()
    a:std.CountTimer(sleep=0.1, start=1, steps=100)
    a.integer > b.in
    """
    result, errors, warnings = parse('inline', script)
    assert len(errors) == 2 
    assert errors[0]['reason'] == "Component Foo has no inport 'foo'" 
    assert errors[1]['reason'] == "Component Foo is missing connection to inport 'in'" 

def testBadComponent6():
    script = """
    component Foo() -> out {
        a:std.CountTimer(sleep=0.1, start=1, steps=100)
        a.integer > .foo
    }
    b:Foo()
    a:test.Sink(store_tokens=false, quiet=false, active=true)
    b.out > a.token
    """
    result, errors, warnings = parse('inline', script)
    assert len(errors) == 2 
    assert errors[0]['reason'] == "Component Foo has no outport 'foo'" 
    assert errors[1]['reason'] == "Component Foo is missing connection to outport 'out'" 

def testBadComponent7():
    script = """
    component Foo() in -> out {
        .in > .out
    }
    """
    result, errors, warnings = parse('inline', script)
    print(errors)
    assert len(errors) == 1 
    assert errors[0]['reason'] == "Component inport connected directly to outport." 



def testUndefinedActors():
    script = """
    a.token > b.token
    """
    result, errors, warnings = parse('inline', script)
    assert len(errors) == 2 
    assert errors[0]['reason'] == "Undefined actor: 'a'" 
    assert errors[1]['reason'] == "Undefined actor: 'b'" 


def testUndefinedArguments():
    script = """
    a:std.Constant()
    b:test.Sink(store_tokens=false, quiet=false, active=true)
    a.token > b.token
    """
    result, errors, warnings = parse('inline', script)
    assert len(errors) == 1 
    assert errors[0]['reason'] == "Missing argument: 'data'" 

def testExcessArguments():
    script = """
    a:std.Constant(data=1, bar=2)
    b:test.Sink(store_tokens=false, quiet=false, active=true)
    a.token > b.token
    """
    result, errors, warnings = parse('inline', script)
    assert len(errors) == 1 
    assert errors[0]['reason'] == "Excess argument: 'bar'" 


def testComponentUndefinedArgument():
    script = """
    component Foo(file) in -> {
        a:test.Sink(store_tokens=false, quiet=false, active=true)
        .in > a.token
    }
    b:Foo()
    a:std.CountTimer(sleep=0.1, start=1, steps=100)
    a.integer > b.in
    """
    result, errors, warnings = parse('inline', script)
    assert len(errors) == 2 
    assert errors[0]['reason'] == "Missing argument: 'file'" 
    assert errors[1]['reason'] == "Unused argument: 'file'" 

def testComponentUnusedArgument():
    script = """
    component Foo(file) in -> {
        a:test.Sink(store_tokens=false, quiet=false, active=true)
        .in > a.token
    }
    b:Foo(file="Foo.txt")
    a:std.CountTimer(sleep=0.1, start=1, steps=100)
    a.integer > b.in
    """
    result, errors, warnings = parse('inline', script)
    assert len(errors) == 1 
    assert errors[0]['reason'] == "Unused argument: 'file'" 

def testComponentExcessArgument():
    script = """
    component Foo(file) -> out {
        file > .out
    }
    a:Foo(file="Foo.txt", bar=1)
    b:io.Print()
    a.out > b.token
    """
    result, errors, warnings = parse('inline', script)
    assert len(errors) == 1 
    assert errors[0]['reason'] == "Excess argument: 'bar'" 


def testLocalComponentRecurse():
    script = """
      component E() in -> out {
      f:std.Identity(dump=false)

      .in > f.token
      f.token > .out
    }
    component B() in -> out {
      e:E()

      .in > e.in
      e.out > .out
    }

    a:std.Counter()
    b:B()
    c:test.Sink(store_tokens=false, quiet=false, active=true)

    a.integer > b.in
    b.out > c.token
    """
    result, errors, warnings = parse('inline', script)
    assert len(errors) == 0 

def testLocalComponentBad():
    script = """
    component B() in -> out {
      e:E()

      .in > e.in
      e.out > .out
    }
    component E() in -> out {
      f:std.Identity(dump=false)

      .in > f.token
      f.token > .out
    }

    a:std.Counter()
    b:B()
    c:test.Sink(store_tokens=false, quiet=false, active=true)

    a.integer > b.in
    b.out > c.token
    """
    result, errors, warnings = parse('inline', script)
    assert len(errors) == 0 

def testLocalBadComponentCauseCrash1():
    script = """
    component Foo() in -> out {
      snk1 : io.Print()
      .in  > snk1.token
    }
    """
    result, errors, warnings = parse('inline', script)
    assert len(errors) == 1 

def testLocalBadComponentCauseCrash2():
    script = """
    component Foo() in -> out {
      snk1 : io.Print()
      .in  > snk1.token
    }
    foo : Foo()
    """
    result, errors, warnings = parse('inline', script)
    assert len(errors) == 3 
    assert errors[0]['reason'] == "Component Foo is missing connection to outport 'out'" 
    assert errors[1]['reason'] == "Component foo (local.Foo) is missing connection to inport 'in'" 
    assert errors[2]['reason'] == "Component foo (local.Foo) is missing connection to outport 'out'" 

def testLocalBadComponentCauseCrash3():
    script = """
    component Foo() in -> out {
      snk1 : io.Print()
      .in  > snk1.token
    }
    foo : Foo()
    1 > foo.in
    """
    result, errors, warnings = parse('inline', script)
    print(errors)
    assert len(errors) == 2 
    assert errors[0]['reason'] == "Component Foo is missing connection to outport 'out'" 
    assert errors[1]['reason'] == "Component foo (local.Foo) is missing connection to outport 'out'" 


def testNoSuchPort():
    script = """
    i:std.Identity(dump=false)
    src:std.CountTimer(sleep=0.1, start=1, steps=100)
    dst:test.Sink(store_tokens=false, quiet=false, active=true)
    src.integer > i.foo
    i.bar > dst.token
    """
    result, errors, warnings = parse('inline', script)
    assert len(errors) == 4 
    assert errors[0]['reason'] == "Actor i (std.Identity) has no inport 'foo'" 
    assert errors[1]['reason'] == "Actor i (std.Identity) has no outport 'bar'" 
    assert errors[2]['reason'] == "Actor i (std.Identity) is missing connection to inport 'token'" 
    assert errors[3]['reason'] == "Actor i (std.Identity) is missing connection to outport 'token'" 

def testRedefineInstance():
    script = """
    i:std.Identity(dump=false)
    src:std.CountTimer(sleep=0.1, start=1, steps=100)
    dst:test.Sink(store_tokens=false, quiet=false, active=true)
    i:std.ClassicDelay(delay=0.2)
    src.integer > i.token
    i.token > dst.token
    """
    result, errors, warnings = parse('inline', script)
    assert len(errors) == 1 
    assert errors[0]['reason'] == "Instance identifier 'i' redeclared" 

def testUndefinedActorInComponent():
    script = """
    component Bug() -> out {
      b.out > .out
    }
    """
    result, errors, warnings = parse('inline', script)
    assert len(errors) == 1 


def testUndefinedConstant():
    script = """
    src : std.Constant(data=FOO)
    snk : test.Sink(store_tokens=false, quiet=false, active=true)
    src.token > snk.token
    """
    result, errors, warnings = parse('inline', script)
    assert len(errors) == 1 
    assert errors[0]['reason'] == "Undefined identifier: 'FOO'" 

@pytest.mark.xfail()
def testUnusedConstant():
    script = """
    define FOO=2
    sink : flow.Terminator()
    1 > sink.void
    """
    result, errors, warnings = parse('inline', script)
    assert len(errors) == 1 
    assert errors[0]['reason'] == "Unused constant: 'FOO'" 


def testDefinedConstant():
    script = """
    define FOO = 42
    src : std.Constant(data=FOO)
    snk : test.Sink(store_tokens=false, quiet=false, active=true)
    src.token > snk.token
    """
    result, errors, warnings = parse('inline', script)
    assert len(errors) == 0 

def testUndefinedRecursiveConstant():
    script = """
    define FOO = BAR
    src : std.Constant(data=FOO)
    snk : test.Sink(store_tokens=false, quiet=false, active=true)
    src.token > snk.token
    """
    result, errors, warnings = parse('inline', script)
    assert len(errors) == 2 
    assert errors[0]['reason'] == "Constant 'BAR' is undefined" 
    assert errors[1]['reason'] == "Undefined identifier: 'FOO'" 


def testDefinedRecursiveConstant():
    script = """
    define FOO = BAR
    define BAR = 42
    src : std.Constant(data=FOO)
    snk : test.Sink(store_tokens=false, quiet=false, active=true)
    src.token > snk.token
    """
    result, errors, warnings = parse('inline', script)
    assert len(errors) == 0 


def testLiteralOnPort():
    script = """
    snk : test.Sink(store_tokens=false, quiet=false, active=true)
    42 > snk.token
    """
    result, errors, warnings = parse('inline', script)
    assert len(errors) == 0 

def testComponentArgumentOnInternalPort():
    script = """
    component Foo(foo) -> out {
        foo > .out
    }
    """
    result, errors, warnings = parse('inline', script)
    assert len(errors) == 0 

def testLiteralOnInternalPort():
    script = """
    component Foo() -> out {
        1 > .out
    }
    """
    result, errors, warnings = parse('inline', script)
    assert len(errors) == 0 


def testBadLocalPort():
    script = """
    component Foo() in -> {
        snk : test.Sink(store_tokens=false, quiet=false, active=true)
        .in > snk.token
    }
    src : std.Counter()
    src.integer > .in
    """
    result, errors, warnings = parse('inline', script)
    assert len(errors) == 1 
    assert errors[0]['reason'] == "Internal port '.in' outside component definition" 


def testVoidOnInPort():
    script = """
    iip : flow.Init(data="ping")
    print : io.Print()
    voidport > iip.in
    iip.out > print.token
    """
    result, errors, warnings = parse('inline', script)
    assert len(errors) == 0 
    assert len(warnings) == 1 
    assert warnings[0]['reason'] == "Using 'void' as input to 'iip.in'" 


def testVoidOnOutPort():
    script = """
    src : std.Counter()
    src.integer > voidport
    """
    result, errors, warnings = parse('inline', script)
    assert len(errors) == 0 

def testVoidInvalidUse1():
    script = """
    component Foo() in -> {
        .in > voidport
    }
    """
    result, errors, warnings = parse('inline', script)
    assert len(errors) == 1 
    assert errors[0]['reason'] == "Syntax error." 

def testVoidInvalidUse2():
    script = """
    component Bar() -> out {
        voidport > .out
    }
    """
    result, errors, warnings = parse('inline', script)
    assert len(errors) == 1 
    assert errors[0]['reason'] == "Syntax error." 

def testVoidInvalidUse3():
    script = """
    1 > voidport
    """
    result, errors, warnings = parse('inline', script)
    assert len(errors) == 1 
    assert errors[0]['reason'] == "Syntax error." 

def testVoidInvalidUse4():
    script = """
    define BAR=1
    BAR > voidport
    """
    result, errors, warnings = parse('inline', script)
    assert len(errors) == 1 
    assert errors[0]['reason'] == "Syntax error." 

def testPortlist2():
    script = """
    src : std.Counter()
    snk1 : io.Print()
    snk2 : io.Print()
    src.integer > snk1.token, snk2.token
    """
    result, errors, warnings = parse('inline', script)
    assert len(errors) == 0 

def testPortlist3():
    script = """
    src : std.Counter()
    snk1 : io.Print()
    snk2 : io.Print()
    snk3 : io.Print()
    src.integer > snk1.token, snk2.token, snk3.token
    """
    result, errors, warnings = parse('inline', script)
    assert len(errors) == 0 

def testPortlistLiteral():
    script = """
    snk1 : io.Print()
    snk2 : io.Print()
    1 > snk1.token, snk2.token
    """
    result, errors, warnings = parse('inline', script)
    assert len(errors) == 0 


def testPortlistInternalOutPort():
    script = """
    component Foo() in ->  {
        snk1 : io.Print()
        snk2 : io.Print()
        .in  > snk1.token , snk2.token
    }
    snk : Foo()
    1 > snk.in
    """
    result, errors, warnings = parse('inline', script)
    assert len(errors) == 0 

def testPortlistInternalInPort():
    script = """
    component Foo() -> out {
        snk1 : io.Print()
        snk2 : io.Print()
        1  > snk1.token, snk2.token, .out
    }
    """
    result, errors, warnings = parse('inline', script)
    assert len(errors) == 0 

def testPortlistInternalInPort2():
    script = """
    component Foo() -> out {
        snk1 : io.Print()
        snk2 : io.Print()
        src : std.Counter()
        src.integer  > snk1.token, snk2.token, .out
    }
    """
    result, errors, warnings = parse('inline', script)
    assert len(errors) == 0 


def testPortlistInternalOutPortPassthrough():
    script = """
    component Foo() in -> out {
        snk1 : io.Print()
        .in  > snk1.token, .out
    }
    """
    result, errors, warnings = parse('inline', script)
    assert len(errors) == 1 
    assert errors[0]['reason'] == "Component inport connected directly to outport." 

def testTokenTransform():
    script = """
    snk1 : io.Print()
    1 > /2/ snk1.token
    """
    result, errors, warnings = parse('inline', script)
    assert len(errors) == 0 

def testTokenTransformBad():
    script = """
    snk1 : io.Print()
    1 /2/ > snk1.token
    """
    result, errors, warnings = parse('inline', script)
    assert len(errors) == 2 

def testTokenTransformInternalInport():
    script = """
    component Foo() in ->  {
        snk1 : io.Print()
        .in  > /2/ snk1.token
    }
    f : Foo()
    1 > f.in
    """
    result, errors, warnings = parse('inline', script)
    assert len(errors) == 0 

def testTokenTransformInternalInportBad():
    script = """
    component Foo() in ->  {
        snk1 : io.Print()
        .in /2/ > snk1.token
    }
    f : Foo()
    1 > f.in
    """
    result, errors, warnings = parse('inline', script)
    assert len(errors) == 3

def testTokenTransformInternalOutport():
    script = """
    component Foo()  -> out {

        1 > /2/ .out
    }
    f : Foo()
    f.out > voidport
    """
    result, errors, warnings = parse('inline', script)
    assert len(errors) == 0 

def testTokenTransformInternalOutportBad():
    script = """
    component Foo()  -> out {

        1 /2/ >  .out
    }
    f : Foo()
    f.out > voidport
    """
    result, errors, warnings = parse('inline', script)
    assert len(errors) == 2 

def testStringLiteral():
    # N.B raw string (r"") required to have same behaviour as script file
    script = r"""
    out: io.Print()
    "{\"x\": \"X\n\"}" > out.token
    """
    result, errors, warnings = parse('inline', script)
    assert len(errors) == 0 

def testStringLiteralNoLinebreaks():
    # N.B raw string (r"") required to have same behaviour as script file
    script = r"""
    define FOO = "abc
                  def"
    """
    result, errors, warnings = parse('inline', script)
    assert len(errors) == 1 

def testStringLiteralConcatenation():
    # N.B raw string (r"") required to have same behaviour as script file
    script = r"""
    define FOO = "abc\n"
                 "def"
    """
    result, errors, warnings = parse('inline', script)
    assert len(errors) == 0 

def testLabelConstant():
    script = r"""
    print1 : io.Print()
    print2 : io.Print()
    :foo 1 > print1.token
    foo.token > print2.token
    """
    result, errors, warnings = parse('inline', script)
    assert len(errors) == 0 

def testLabelConstantify():
    script = r"""
    print1 : io.Print()
    print2 : io.Print()
    1 > /:foo 2/ print1.token
    foo.out > print2.token
    """
    result, errors, warnings = parse('inline', script)
    assert len(errors) == 0 

def testPortRef():
    script = r"""
    print1 : io.Print()
    &print1.token >  print1.token
    """
    result, errors, warnings = parse('inline', script)
    assert len(errors) == 0 

@pytest.mark.xfail()
def testPortRefMissingSyntaxCheck():
    # FIXME: io.Print has no outport
    script = r"""
    print1 : io.Print()
    &print1.token[out] >  print1.token
    """
    result, errors, warnings = parse('inline', script)
    assert len(errors) == 1 

@pytest.mark.xfail()
def testPortRefAsKey():
    script = r"""
    print1 : io.Print()
    {&print1.token:"Comment"} >  print1.token
    """
    result, errors, warnings = parse('inline', script)
    self.assertTrue(len(errors) > 0)

# def testAmbigousPortProperty1():
#     script = r"""
#     i : std.Identity(dump=false)
#     src : std.CountTimer(sleep=0.1, start=1, steps=100)
#     snk : io.Print()
#     src.integer > i.token
#     i.token > snk.token
#     i.token(routing="round-robin")
#     """
#     result, errors, warnings = parse('inline', script)
#     assert len(errors) == 2 

# def testAmbigousPortProperty2():
#     script = r"""
#     i : std.Identity(dump=false)
#     src : std.CountTimer(sleep=0.1, start=1, steps=100)
#     snk : io.Print()
#     src.integer > i.token
#     i.token > snk.token
#     i.token[in](routing="round-robin")
#     """
#     result, errors, warnings = parse('inline', script)
#     assert len(errors) == 1 

# def testAmbigousPortProperty3():
#     script = r"""
#     i : std.Identity(dump=false)
#     src : std.CountTimer(sleep=0.1, start=1, steps=100)
#     snk : io.Print()
#     src.integer > i.token
#     i.token > snk.token
#     i.token[out](routing="round-robin")
#     """
#     result, errors, warnings = parse('inline', script)
#     assert len(errors) == 0 

def testComponentToComponent1():
    script = r"""
    component InComp() in -> {
        out : io.Print()
        .in > out.token
    }

    component OutComp() -> out {
        trig : std.Trigger(data="No data", tick=1.0)
        trig.data > .out
    }

    out_comp : OutComp()
    in_comp : InComp()

    out_comp.out > in_comp.in
    """
    result, errors, warnings = parse('inline', script)
    for e in errors:
        print(e['reason'])
    assert len(errors) == 0 

def testCompToCompWithFanoutFromInternalInport():
    script = r"""
    component Left() -> out {
        src : std.Trigger(tick=1, data=true)
        src.data > .out
    }
    component Right() in ->  {
        a : io.Print()
        b : io.Print()
        .in > a.token, b.token
    }
    src : Left()
    snk : Right()
    src.out > snk.in
    """
    result, errors, warnings = parse('inline', script)
    for e in errors:
        print(e['reason'])
    assert len(errors) == 0 




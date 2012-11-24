from cellaserv.service import Service

class Test(Service):

    @Service.action
    def foo(self):
        return "bar"

    @Service.action
    def echo(self, str):
        return str

def main():
    tf = Test("foo")
    tf.setup()
    tb = Test("bar")
    tb.setup()

    Service.loop()

if __name__ == '__main__':
    main()

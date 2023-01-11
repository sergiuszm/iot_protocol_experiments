from flask import Flask, request, Response #import main Flask class and request object
import os

PORT = 31415

MSG_TYPE={
    'short': b"It is a simple short response.\n",
    'middle': b"Lorem ipsum dolor sit amet, consectetur adipiscing elit. Integer nisl magna, varius et nunc ut, pharetra posuere ante. "\
            b"Praesent vestibulum tempor vehicula. Nunc vehicula a elit at rhoncus. Proin luctus ex at sapien pretium, a consequat magna maximus. "\
            b"Nunc scelerisque nunc et enim pellentesque, eu porta diam aliquet. Mauris mollis congue justo, ac volutpat nibh consequat sit amet. "\
            b"Vestibulum ante ipsum primis in faucibus orci luctus et ultrices posuere cubilia curae; Curabitur congue nibh ut efficitur est.\n\n",
    'long': b"Lorem ipsum dolor sit amet, consectetur adipiscing elit. Integer quam nulla, tincidunt nec dolor ut, "\
            b"convallis finibus est. Aenean pretium nulla eu dolor ultrices maximus. Phasellus laoreet metus et pellentesque ornare. "\
            b"Praesent ac purus sed quam pulvinar cursus. Suspendisse dictum mollis est non tincidunt. In posuere mauris justo, "\
            b"nec rhoncus tortor vestibulum at. Aenean in lorem augue. Maecenas ante elit, tempor id ante in, pellentesque congue nisl.\n\n"\
            b"Curabitur sit amet pulvinar turpis. Suspendisse potenti. Aenean porta, arcu sed sollicitudin commodo, ante dolor suscipit eros, "\
            b"vitae eleifend velit felis ac risus. Sed vehicula mi sed ultrices ullamcorper. Nulla fringilla ac lacus viverra egestas. "\
            b"Suspendisse metus ligula, ultricies et egestas in, sodales vitae nunc. Quisque aliquam dolor fringilla venenatis aliquam. "\
            b"Praesent tellus diam, luctus eu risus in, scelerisque auctor nunc. Donec odio nibh, venenatis eget condimentum eu, tristique "\
            b"facilisis nunc. Proin arcu ex, congue malesuada consequat a, tempor eu justo. Vivamus sapien magna, venenatis at interdum ut, "\
            b"eleifend eget velit.\n\n"\
            b"Sed a efficitur eros. Vestibulum mattis blandit malesuada. Donec leo quam, facilisis ac tortor eu, fringilla tempus neque. "\
            b"Vestibulum volutpat, diam vel vulputate molestie, nunc velit mollis ipsum, vitae pulvinar urna neque nec leo. Curabitur elit tortor, "\
            b"venenatis sed malesuada at, efficitur quis risus. Fusce ac tellus et ipsum viverra consequat. Proin pretium commodo lacus, "\
            b"quis vestibulum nisl consequat eu. Morbi maximus, neque in tempus finibus, lacus odio tempus magna, sit amet pretium libero.\n\n"
}

app = Flask(__name__) #create the Flask app

@app.route('/<name>', methods=['GET', 'POST'])
def short(name):
    if name not in MSG_TYPE:
        return 'R_ERR', 404

    if request.method == 'POST':
        # print(request.headers)
        data = request.files['file']
        file_status = 'NOT_OK'
        payload = data.read()
        if payload == MSG_TYPE[name]:
            file_status = 'OK'

        print(f'[{request.remote_addr}][POST: /{name}][{request.content_length}B][{len(payload)}B][{file_status}]')

        if file_status == 'NOT_OK':
            return 'R_ERR', 400

        return 'R_OK', 200
    
    if request.method == 'GET':
        print(f'[{request.remote_addr}][GET: /{name}][{len(MSG_TYPE[name])}B]')
        return Response(MSG_TYPE[name], mimetype='text/plain')


if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=PORT)
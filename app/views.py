from flask import render_template, redirect, url_for, session, request

from app import app, monitor, q
from app.forms import PhoneForm, ConfirmationForm, AddChannelsForm
from app.models import ChannelChain


@app.before_request
def check_authorization():
    # Check if user is not authorized
    if not monitor.client.is_user_authorized():
        if (request.endpoint != 'login') and (request.endpoint != 'confirm'):
            # Try get the session name
            phone = session.get('phone', None)
            print(phone)
            if phone is not None:
                # If monitor does not send code (returns False), then the user authorization is done.
                # Otherwise user will get the code from Telegram and he have confirm it.
                if monitor.send_code(phone=phone):
                    return redirect(url_for('confirm'))
            else:
                # Redirect to the login page so the phone (name of the session) has not be found.
                if request.endpoint != 'login':
                    return redirect(url_for('login'))


@app.route('/')
def index():
    chains = ChannelChain.query.all()
    return render_template('index.html', chains=chains)


def background_task(phone):
    monitor.start_monitoring(phone)

@app.route('/start_work')
def start_work():
    # Clear the queue
    for job in q.get_jobs():
        job.kill()

    # Begin a new asynchronous job
    phone = session.get('phone', None)
    job = q.enqueue_call(func=background_task, args=(phone,), timeout='10000h')
    print(job.get_id())

    # Redirect to the main page
    return redirect(url_for('index'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = PhoneForm()
    if form.validate_on_submit():
        # Get a phone number from the POST-request
        phone = form.phone.data

        # Save the phone into the session
        session['phone'] = phone

        # Setup the client
        if monitor.send_code(phone=phone):
            return redirect(url_for('confirm'))
        else:
            return redirect(url_for('index'))

    # Render the login template with the PhoneForm()
    return render_template('login.html', form=form)


@app.route('/confirm', methods=['GET', 'POST'])
def confirm():
    form = ConfirmationForm()
    if form.validate_on_submit():
        code = int(form.code.data)

        # Confirm the code
        monitor.confirm(code=code)
        return redirect(url_for('index'))

    # Render the confirm template with the ConfirmationForm()
    return render_template('confirm.html', form=form)


@app.route('/add_channels', methods=['GET', 'POST'])
def add_chain():
    error = None
    form = AddChannelsForm()
    if form.validate_on_submit():
        # Get names of needed channels
        from_channel_name = form.outgoing.data
        to_channel_name = form.incoming.data

        # Try to add channel chain into the database
        result = monitor.add_chain(from_channel_name=from_channel_name, to_channel_name=to_channel_name)
        if result == True:
            return redirect(url_for('start_work'))
        else:
            error = result
    return render_template('add_channel.html', form=form, error=error)

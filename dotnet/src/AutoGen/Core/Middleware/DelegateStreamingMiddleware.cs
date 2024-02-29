﻿// Copyright (c) Microsoft Corporation. All rights reserved.
// DelegateStreamingMiddleware.cs

using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;

namespace AutoGen.Core.Middleware;

internal class DelegateStreamingMiddleware : IStreamingMiddleware
{
    public delegate Task<IAsyncEnumerable<IMessage>> MiddlewareDelegate(
        MiddlewareContext context,
        IStreamingAgent agent,
        CancellationToken cancellationToken);

    private readonly MiddlewareDelegate middlewareDelegate;

    public DelegateStreamingMiddleware(string? name, MiddlewareDelegate middlewareDelegate)
    {
        this.Name = name;
        this.middlewareDelegate = middlewareDelegate;
    }

    public string? Name { get; }

    public Task<IAsyncEnumerable<IMessage>> InvokeAsync(
               MiddlewareContext context,
               IStreamingAgent agent,
               CancellationToken cancellationToken = default)
    {
        var messages = context.Messages;
        var options = context.Options;

        return this.middlewareDelegate(context, agent, cancellationToken);
    }
}

